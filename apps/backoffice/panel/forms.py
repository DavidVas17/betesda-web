from urllib.parse import urlsplit

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

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
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True, is_staff=True
        ).order_by("first_name", "username")
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


class TeamUserCreateForm(UserCreationForm):
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

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = False
        user.role = User.Role.EDITOR
        if commit:
            user.save()
        return user


class TeamUserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active")
        labels = TeamUserCreateForm.Meta.labels
        help_texts = TeamUserCreateForm.Meta.help_texts

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = False
        user.role = User.Role.EDITOR
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
        }
