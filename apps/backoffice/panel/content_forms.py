from django import forms

from apps.events.models import Event
from apps.gallery.forms import MAX_FILE_MB
from apps.gallery.models import Album, Photo
from apps.news.models import Post

DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


class LocalDateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format=DATETIME_FORMAT, **kwargs)


class PanelImageField(forms.ImageField):
    def __init__(self, **kwargs):
        kwargs.setdefault("widget", forms.ClearableFileInput(attrs={"accept": "image/*"}))
        kwargs.setdefault("help_text", f"Imagen JPG, PNG o WebP de hasta {MAX_FILE_MB} MB.")
        super().__init__(**kwargs)

    def clean(self, data, initial=None):
        if data and getattr(data, "size", 0) > MAX_FILE_MB * 1024 * 1024:
            raise forms.ValidationError(
                f"La imagen supera los {MAX_FILE_MB} MB. Reduce su tamaño e inténtalo de nuevo.",
                code="too_big",
            )
        return super().clean(data, initial)


class PanelModelForm(forms.ModelForm):
    def __init__(self, *args, readonly=False, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "panel-input")
            if isinstance(field, forms.DateTimeField):
                field.input_formats = [DATETIME_FORMAT, *field.input_formats]
            if readonly:
                field.disabled = True


class EventForm(PanelModelForm):
    cover_image = PanelImageField(label="Imagen de portada", required=False)

    class Meta:
        model = Event
        fields = (
            "title",
            "summary",
            "description",
            "starts_at",
            "ends_at",
            "location",
            "cover_image",
            "is_published",
            "is_featured",
        )
        labels = {
            "title": "Nombre del evento",
            "summary": "Resumen para la tarjeta",
            "description": "Detalles del evento",
            "starts_at": "Fecha y hora de inicio",
            "ends_at": "Fecha y hora de finalización",
            "location": "Lugar",
            "is_published": "Publicar en el sitio web",
            "is_featured": "Destacar en Inicio",
        }
        help_texts = {
            "summary": "Una descripción breve de hasta 280 caracteres.",
            "starts_at": "Hora local de Guatemala.",
            "ends_at": "Déjala vacía si todavía no hay hora de finalización.",
            "is_published": "Si está desmarcado, solo el equipo puede ver este evento.",
            "is_featured": "Los eventos destacados tienen prioridad en Inicio.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 8}),
            "summary": forms.Textarea(attrs={"rows": 2}),
            "starts_at": LocalDateTimeInput(),
            "ends_at": LocalDateTimeInput(),
        }


class PostForm(PanelModelForm):
    cover_image = PanelImageField(label="Imagen de portada", required=False)

    class Meta:
        model = Post
        fields = (
            "title",
            "excerpt",
            "body",
            "cover_image",
            "status",
            "published_at",
            "is_featured",
        )
        labels = {
            "title": "Título de la noticia",
            "excerpt": "Resumen para la tarjeta",
            "body": "Contenido de la noticia",
            "status": "Estado de publicación",
            "published_at": "Fecha y hora de publicación",
            "is_featured": "Destacar en Inicio",
        }
        help_texts = {
            "excerpt": "Una descripción breve de hasta 280 caracteres.",
            "status": "Los borradores y las noticias archivadas no aparecen en el sitio público.",
            "published_at": (
                "Hora local de Guatemala. Al publicar sin fecha se usa la hora actual. "
                "Una fecha futura programa la noticia para ese momento."
            ),
            "is_featured": "Las noticias destacadas tienen prioridad en Inicio.",
        }
        widgets = {
            "excerpt": forms.Textarea(attrs={"rows": 2}),
            "body": forms.Textarea(attrs={"rows": 12}),
            "published_at": LocalDateTimeInput(),
        }


class AlbumForm(PanelModelForm):
    class Meta:
        model = Album
        fields = ("title", "description", "event_date", "is_published")
        labels = {
            "title": "Nombre del álbum",
            "description": "Descripción",
            "event_date": "Fecha de la actividad",
            "is_published": "Publicar en la galería",
        }
        help_texts = {
            "is_published": "Las fotografías del álbum se mostrarán en el sitio público.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "event_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }


class PhotoForm(PanelModelForm):
    image = PanelImageField(label="Fotografía")

    class Meta:
        model = Photo
        fields = ("image", "alt_text", "caption", "order")
        labels = {
            "alt_text": "¿Qué aparece en la fotografía?",
            "caption": "Descripción visible",
            "order": "Orden en el álbum",
        }
        help_texts = {
            "alt_text": "Descripción breve para personas que usan lectores de pantalla.",
            "order": "Las fotografías con el número menor aparecen primero.",
        }
