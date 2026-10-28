import logging
from urllib.parse import urlsplit

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse

from apps.accounts.roles import (
    PRIVILEGED_ROLE_NAMES,
    ROLE_NAMES,
    ROLES,
    set_user_roles,
    user_role_names,
)
from apps.accounts.throttle import (
    TOO_MANY_ATTEMPTS,
    ThrottledLoginMixin,
    record_failure,
    seconds_until_allowed,
)
from apps.contacts.models import ContactMessage
from apps.core.emails import Email
from apps.core.models import SiteConfiguration
from apps.core.network import client_ip

from .content_forms import choice_label
from .form_layout import FieldsetsMixin

User = get_user_model()

logger = logging.getLogger(__name__)


class PanelAuthenticationForm(ThrottledLoginMixin, AuthenticationForm):
    username = forms.CharField(
        label="Usuario",
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError("Esta cuenta no tiene acceso al panel.", code="not_staff")


class PanelPasswordResetForm(PasswordResetForm):
    """Solo cuentas activas del equipo, y con el mismo freno que el ingreso.

    Cada pedido cuenta como un intento: así nadie puede usar el formulario para llenar de
    correos la bandeja de otra persona.
    """

    email = forms.EmailField(
        label="Correo electrónico",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}),
    )

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"]
        key = f"reset:{email}"
        ip = client_ip(self.request) if self.request else None
        wait = seconds_until_allowed(key, ip)
        if wait:
            minutes = max(1, -(-wait // 60))
            raise forms.ValidationError(
                TOO_MANY_ATTEMPTS,
                code="too_many_attempts",
                params={"minutes": f"{minutes} minuto" + ("s" if minutes != 1 else "")},
            )
        record_failure(key, ip, request=self.request)
        return email

    def get_users(self, email):
        return (user for user in super().get_users(email) if user.is_staff)

    def send_mail(self, subject_template_name, email_template_name, context, *args, **kwargs):
        """El enlace sale con el diseño de los correos del sitio (HTML y texto)."""
        user = context["user"]
        link = (
            context["protocol"]
            + "://"
            + context["domain"]
            + reverse(
                "panel:password_reset_confirm",
                kwargs={"uidb64": context["uid"], "token": context["token"]},
            )
        )
        hours = context.get("timeout_hours", 2)
        email = Email(
            subject="".join(render_to_string(subject_template_name, context).splitlines()),
            eyebrow="Panel de la iglesia",
            title="Restablece tu contraseña",
            preheader="Usa este enlace para elegir una contraseña nueva.",
            paragraphs=[
                f"Hola {user.get_short_name() or user.get_username()}:",
                "Alguien pidió restablecer la contraseña de tu cuenta del panel de Betesda "
                "Rosa de Sarón. Si fuiste tú, usa el botón para elegir una contraseña nueva.",
            ],
            details=[
                ("Tu usuario", user.get_username()),
                ("El enlace vence en", f"{hours} hora{'s' if hours != 1 else ''}"),
            ],
            button=("Elegir contraseña nueva", link),
            note="Si no lo pediste, ignora este correo: tu contraseña no cambia. El enlace "
            "funciona una sola vez.",
            footer="Por seguridad, nunca te pediremos tu contraseña por correo.",
        )
        try:
            email.message(to=[user.email]).send()
        except Exception:  # noqa: BLE001 - igual que Django: se registra y no se revela
            logger.exception("No se pudo enviar el correo de recuperación a %s", user.pk)


class PanelSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("new_password1", "new_password2"):
            self.fields[name].widget.attrs["autocomplete"] = "new-password"
        self.fields["new_password1"].label = "Contraseña nueva"
        self.fields["new_password2"].label = "Confirma la contraseña nueva"


class MessageFollowupForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ("status", "assigned_to", "internal_notes")
        labels = {
            "status": "Estado de la solicitud",
            "assigned_to": "Persona responsable",
            "internal_notes": "Notas del equipo",
        }
        help_texts = {
            "assigned_to": "Elige quién acompañará esta solicitud.",
            "internal_notes": "Estas notas son privadas. La persona que escribió no las recibe.",
        }
        widgets = {"internal_notes": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo quien puede leer mensajes puede acompañar una solicitud: una petición de
        # oración no debe quedar a cargo de alguien que ni siquiera puede abrirla.
        can_read = {"content_type__app_label": "contacts", "codename": "view_contactmessage"}
        readers = Permission.objects.filter(**can_read)
        self.fields["assigned_to"].queryset = (
            User.objects.filter(is_active=True, is_staff=True)
            .filter(
                Q(is_superuser=True)
                | Q(groups__permissions__in=readers)
                | Q(user_permissions__in=readers)
            )
            .distinct()
            .order_by("first_name", "username")
        )
        self.fields["assigned_to"].empty_label = "Sin asignar"


class SiteSettingsForm(FieldsetsMixin, forms.ModelForm):
    fieldsets = (
        ("Identidad", "Cómo se presenta la iglesia en el sitio.", ("institution_name", "slogan")),
        ("Contacto", "Por dónde nos encuentra la comunidad.", ("phone", "email", "address")),
        ("Enlaces", "Copia los enlaces completos desde el navegador.", ("facebook_url", "map_url")),
        (
            "Quiénes somos",
            "Estos textos aparecen en Inicio y en Nosotros.",
            ("mission", "vision", "purpose", "history"),
        ),
    )

    class Meta:
        model = SiteConfiguration
        fields = (
            "institution_name",
            "slogan",
            "phone",
            "email",
            "address",
            "facebook_url",
            "map_url",
            "mission",
            "vision",
            "purpose",
            "history",
        )
        labels = {
            "institution_name": "Nombre de la iglesia",
            "slogan": "Lema",
            "phone": "Teléfono",
            "email": "Correo de la iglesia",
            "address": "Dirección",
            "facebook_url": "Página de Facebook",
            "map_url": "Enlace de Google Maps",
            "mission": "Misión",
            "vision": "Visión",
            "purpose": "Propósito",
            "history": "Historia",
        }
        help_texts = {
            "email": "Opcional. Se mostrará en la página de Contacto cuando lo completes.",
            "map_url": "Pega el enlace para compartir la ubicación de la iglesia.",
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "mission": forms.Textarea(attrs={"rows": 4}),
            "vision": forms.Textarea(attrs={"rows": 4}),
            "purpose": forms.Textarea(attrs={"rows": 4}),
            "history": forms.Textarea(attrs={"rows": 6}),
        }

    def clean_facebook_url(self):
        return self._secure_link("facebook_url")

    def clean_map_url(self):
        return self._secure_link("map_url")

    def _secure_link(self, field):
        value = self.cleaned_data.get(field, "")
        if value and urlsplit(value).scheme != "https":
            raise forms.ValidationError("Usa un enlace seguro que empiece por https://.")
        return value


class TeamRolesMixin(FieldsetsMixin):
    """Casillas de roles para las cuentas del equipo, con las reglas de quién asigna qué.

    - Solo el superusuario asigna o quita roles privilegiados (Administración de la iglesia).
    - Nadie cambia sus propios roles ni desactiva su propia cuenta.
    - Ninguna cuenta creada o editada aquí es superusuario.
    """

    fieldsets = (
        (
            "Datos de la persona",
            "Cómo aparecerá en el panel.",
            ("first_name", "last_name", "email"),
        ),
        (
            "Acceso",
            "El usuario es con lo que ingresa. Una cuenta inactiva no puede entrar.",
            ("username", "password1", "password2", "is_active"),
        ),
        ("Roles", "Marca lo que esta persona va a manejar.", ("roles",)),
    )

    def _setup_roles(self, actor):
        self.actor = actor
        self.editing_self = bool(self.instance.pk and actor and self.instance.pk == actor.pk)
        self.current_roles = user_role_names(self.instance) if self.instance.pk else []
        self.fields["roles"] = forms.MultipleChoiceField(
            label="Roles en el panel",
            choices=[(role.name, choice_label(role.name, role.description)) for role in ROLES],
            required=False,
            widget=forms.CheckboxSelectMultiple,
            initial=self.current_roles,
            help_text=(
                "Los permisos de varios roles se suman. "
                + (
                    ""
                    if actor is not None and actor.is_superuser
                    else "Solo el superadministrador asigna Administración de la iglesia."
                )
            ).strip(),
        )
        if self.editing_self:
            self.fields["roles"].disabled = True
            self.fields["roles"].help_text = "No puedes cambiar tus propios roles."
            self.fields["is_active"].disabled = True
            self.fields["is_active"].help_text = "No puedes desactivar tu propia cuenta."

    def clean_roles(self):
        if self.editing_self:
            return self.current_roles
        wanted = set(self.cleaned_data.get("roles") or [])
        if not (self.actor is not None and self.actor.is_superuser):
            current = set(self.current_roles)
            for name in PRIVILEGED_ROLE_NAMES:
                if (name in wanted) != (name in current):
                    raise forms.ValidationError(
                        f"Solo el superadministrador puede asignar o quitar el rol {name}."
                    )
        return [name for name in ROLE_NAMES if name in wanted]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = False
        if commit:
            user.save()
            set_user_roles(user, self.cleaned_data["roles"])
        return user


class TeamUserCreateForm(TeamRolesMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active")
        labels = {
            "username": "Nombre de usuario",
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
            "is_active": "Cuenta activa",
        }
        help_texts = {"is_active": "Las cuentas activas pueden entrar al panel."}

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_roles(actor)


class TeamUserEditForm(TeamRolesMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active")
        labels = TeamUserCreateForm.Meta.labels
        help_texts = TeamUserCreateForm.Meta.help_texts

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_roles(actor)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "notify_new_messages")
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
            "notify_new_messages": "Avisarme por correo de mensajes nuevos",
        }
        help_texts = {
            "notify_new_messages": "Te llega un aviso, sin el contenido, cuando alguien escribe "
            "en el sitio. Necesitas tener tu correo guardado arriba.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo tiene sentido para quien puede leer los mensajes.
        if not self.instance.has_perm("contacts.view_contactmessage"):
            self.fields.pop("notify_new_messages")
