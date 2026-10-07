import re

from django import forms
from django.core.exceptions import ValidationError

from .models import ContactMessage
from .modes import CONTACT_MODES


class ContactMessageForm(forms.ModelForm):
    message = forms.CharField(
        label="Tu petición o mensaje",
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Cuéntanos cómo podemos ayudarte."}),
        help_text="Máximo 5,000 caracteres.",
    )
    privacy_accepted = forms.BooleanField(
        label="Acepto que utilicen mis datos para atender esta solicitud y contactarme.",
        error_messages={"required": "Debes aceptar el uso de tus datos para enviar tu solicitud."},
        help_text=(
            "Usaremos tus datos de contacto y tu mensaje para atender tu solicitud. "
            "El mensaje y tus datos de contacto no se publican en el sitio."
        ),
    )
    website = forms.CharField(
        label="Sitio web",
        required=False,
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    class Meta:
        model = ContactMessage
        fields = ("kind", "name", "email", "phone", "subject", "message", "privacy_accepted")
        labels = {
            "name": "Nombre completo",
            "email": "Correo electrónico",
            "phone": "Número de teléfono",
            "subject": "Asunto",
        }
        widgets = {
            "kind": forms.HiddenInput(),
            "name": forms.TextInput(
                attrs={"autocomplete": "name", "placeholder": "Escribe tu nombre completo"}
            ),
            "email": forms.EmailInput(
                attrs={"autocomplete": "email", "placeholder": "tucorreo@ejemplo.com"}
            ),
            "phone": forms.TextInput(
                attrs={
                    "type": "tel",
                    "autocomplete": "tel",
                    "inputmode": "tel",
                    "placeholder": "+502 4171-3008",
                }
            ),
            "subject": forms.TextInput(attrs={"placeholder": "Motivo de tu solicitud"}),
        }
        error_messages = {
            "kind": {
                "required": "Selecciona un tipo de solicitud.",
                "invalid_choice": "Selecciona un tipo de solicitud válido.",
            },
            "name": {"required": "Escribe tu nombre."},
            "email": {
                "required": "Escribe tu correo electrónico.",
                "invalid": "Escribe un correo electrónico válido.",
            },
            "subject": {"required": "Escribe el asunto de tu solicitud."},
        }

    def __init__(self, *args, kind=ContactMessage.Kind.CONTACT, **kwargs):
        super().__init__(*args, **kwargs)
        selected = self.data.get("kind", kind) if self.is_bound else kind
        self.mode = CONTACT_MODES.get(selected, CONTACT_MODES[kind])
        self.fields["kind"].initial = self.mode["kind"]
        for name, label in self.mode["labels"].items():
            self.fields[name].label = label
        for name, placeholder in self.mode["placeholders"].items():
            self.fields[name].widget.attrs["placeholder"] = placeholder
        self.fields["privacy_accepted"].help_text = self.mode["privacy"]

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("website"):
            raise ValidationError("No se pudo enviar el mensaje. Intenta de nuevo.")
        return cleaned_data

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "")
        if phone and (
            not re.fullmatch(r"\+?[0-9 ().-]+", phone)
            or not 7 <= sum(character.isdigit() for character in phone) <= 15
        ):
            raise ValidationError("Escribe un teléfono válido, por ejemplo +502 4171-3008.")
        return phone
