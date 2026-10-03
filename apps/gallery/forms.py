from django import forms

MAX_FILES = 30
MAX_FILE_MB = 8


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """Campo de imagen que acepta varios archivos y valida cada uno con Pillow."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/*"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        files = data if isinstance(data, list | tuple) else [data]
        files = [item for item in files if item]
        if not files:
            if self.required:
                raise forms.ValidationError(self.error_messages["required"], code="required")
            return []
        if len(files) > MAX_FILES:
            raise forms.ValidationError(
                f"Selecciona como máximo {MAX_FILES} fotografías por carga.", code="too_many"
            )
        cleaned = []
        for item in files:
            if item.size > MAX_FILE_MB * 1024 * 1024:
                raise forms.ValidationError(
                    f"«{item.name}» pesa más de {MAX_FILE_MB} MB. "
                    "Reduce su tamaño e inténtalo de nuevo.",
                    code="too_big",
                )
            cleaned.append(single_clean(item, initial))
        return cleaned


class BulkPhotoUploadForm(forms.Form):
    images = MultipleImageField(
        label="Fotografías",
        help_text=f"Hasta {MAX_FILES} imágenes por carga, de máximo {MAX_FILE_MB} MB cada una.",
    )
    alt_text = forms.CharField(
        label="Texto alternativo común",
        max_length=150,
        required=False,
        help_text=(
            "Describe brevemente las fotos para personas con lectores de pantalla. "
            "Si lo dejas vacío se usará «Fotografía de» y el nombre del álbum; "
            "luego puedes afinar cada una."
        ),
    )

    class Media:
        js = ("backoffice/js/photo_upload.js",)
