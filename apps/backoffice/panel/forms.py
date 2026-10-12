from urllib.parse import urlsplit

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Permission
from django.db.models import Q

from apps.accounts.roles import (
    PRIVILEGED_ROLE_NAMES,
    ROLE_NAMES,
    ROLES,
    set_user_roles,
    user_role_names,
)
from apps.contacts.models import ContactMessage
from apps.core.models import SiteConfiguration

User = get_user_model()


class PanelAuthenticationForm(AuthenticationForm):
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


class SiteSettingsForm(forms.ModelForm):
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
        )
        labels = {
            "institution_name": "Nombre de la iglesia",
            "slogan": "Lema",
            "phone": "Teléfono",
            "email": "Correo de la iglesia",
            "address": "Dirección",
            "facebook_url": "Página de Facebook",
            "map_url": "Enlace de Google Maps",
        }
        help_texts = {
            "email": "Opcional. Se mostrará en la página de Contacto cuando lo completes.",
            "map_url": "Pega el enlace para compartir la ubicación de la iglesia.",
        }
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}

    def clean_facebook_url(self):
        return self._secure_link("facebook_url")

    def clean_map_url(self):
        return self._secure_link("map_url")

    def _secure_link(self, field):
        value = self.cleaned_data.get(field, "")
        if value and urlsplit(value).scheme != "https":
            raise forms.ValidationError("Usa un enlace seguro que empiece por https://.")
        return value


class TeamRolesMixin:
    """Casillas de roles para las cuentas del equipo, con las reglas de quién asigna qué.

    - Solo el superusuario asigna o quita roles privilegiados (Administración de la iglesia).
    - Nadie cambia sus propios roles ni desactiva su propia cuenta.
    - Ninguna cuenta creada o editada aquí es superusuario.
    """

    def _setup_roles(self, actor):
        self.actor = actor
        self.editing_self = bool(self.instance.pk and actor and self.instance.pk == actor.pk)
        self.current_roles = user_role_names(self.instance) if self.instance.pk else []
        self.fields["roles"] = forms.MultipleChoiceField(
            label="Roles en el panel",
            choices=[(role.name, f"{role.name}: {role.description}") for role in ROLES],
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
        fields = ("first_name", "last_name", "email")
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
        }
