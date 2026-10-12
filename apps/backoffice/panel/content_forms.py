from django import forms
from django.utils.html import format_html

from apps.events.models import Event
from apps.gallery.forms import MAX_FILE_MB
from apps.gallery.models import Album, Photo
from apps.news.models import Post

from .form_layout import FieldsetsMixin

DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


def choice_label(title, description):
    """Etiqueta de dos líneas para las opciones que se muestran como tarjetas."""
    return format_html("<strong>{}</strong><span>{}</span>", title, description)


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


class PanelModelForm(FieldsetsMixin, forms.ModelForm):
    # Campos que deciden qué se ve en el sitio. Sin permiso de publicar se quitan del
    # formulario: Django ignora lo que llegue en esos nombres y el elemento sigue en borrador.
    publication_fields: tuple[str, ...] = ()

    def __init__(self, *args, readonly=False, can_publish=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_publish:
            for name in self.publication_fields:
                self.fields.pop(name, None)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "panel-input")
            if isinstance(field, forms.DateTimeField):
                field.input_formats = [DATETIME_FORMAT, *field.input_formats]
            if readonly:
                field.disabled = True


class EventForm(PanelModelForm):
    publication_fields = ("is_published", "is_featured")
    fieldsets = (
        ("Lo básico", "El nombre y una idea rápida de la actividad.", ("title", "summary")),
        (
            "Fecha y lugar",
            "Cuándo y dónde nos reunimos. Usa la hora local de Guatemala.",
            ("starts_at", "ends_at", "location"),
        ),
        ("Detalles", "Lo que la persona necesita saber para asistir.", ("description",)),
        ("Imagen", "Una foto horizontal se ve mejor en las tarjetas.", ("cover_image",)),
        ("Publicación", "Decide si ya se muestra en el sitio.", ("is_published", "is_featured")),
    )
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
            "starts_at": LocalDateTimeInput(attrs={"data-starts": ""}),
            "ends_at": LocalDateTimeInput(attrs={"data-ends": ""}),
        }


class PostForm(PanelModelForm):
    publication_fields = ("status", "published_at", "is_featured")
    fieldsets = (
        ("Lo básico", "Un título claro y un resumen para la tarjeta.", ("title", "excerpt")),
        (
            "Contenido",
            "Escribe la noticia completa. Deja una línea en blanco entre párrafos.",
            ("body",),
        ),
        ("Imagen", "Una foto horizontal se ve mejor en las tarjetas.", ("cover_image",)),
        (
            "Publicación",
            "Elige cuándo y cómo se muestra en el sitio.",
            ("status", "published_at", "is_featured"),
        ),
    )
    STATUS_HELP = {
        Post.Status.DRAFT: "Solo el equipo la ve.",
        Post.Status.PUBLISHED: "Se muestra en el sitio.",
        Post.Status.ARCHIVED: "Se retira del sitio y se conserva.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        status = self.fields.get("status")
        if status is not None:
            status.widget = forms.RadioSelect(attrs={"class": "panel-input"})
            status.choices = [
                (value, choice_label(label, self.STATUS_HELP[value]))
                for value, label in Post.Status.choices
            ]
            status.widget.choices = status.choices
            if self.fields["status"].disabled:
                status.widget.attrs["disabled"] = True
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
    publication_fields = ("is_published",)
    fieldsets = (
        ("Lo básico", "Cómo se llama el álbum y de cuándo son las fotos.", ("title", "event_date")),
        ("Descripción", "Unas palabras sobre la actividad.", ("description",)),
        ("Publicación", "Decide si ya se muestra en la galería.", ("is_published",)),
    )

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
    fieldsets = (
        ("Fotografía", "Puedes reemplazar la imagen si hace falta.", ("image",)),
        (
            "Descripción",
            "Ayuda a quienes usan lectores de pantalla y da contexto a todos.",
            ("alt_text", "caption", "order"),
        ),
    )

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
