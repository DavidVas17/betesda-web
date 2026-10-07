from django.contrib import admin, messages
from django.utils import timezone

from apps.backoffice.utils import badge, count_message, preview_html, thumbnail_html

from .models import Post

STATUS_TONES = {
    Post.Status.DRAFT: "warn",
    Post.Status.PUBLISHED: "ok",
    Post.Status.ARCHIVED: "neutral",
}
WORDS_PER_MINUTE = 200


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "thumbnail",
        "title",
        "status_badge",
        "published_at",
        "author",
        "is_featured",
    )
    list_display_links = ("title",)
    list_editable = ("is_featured",)
    list_filter = ("status", "is_featured", "published_at", "author")
    list_select_related = ("author",)
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    readonly_fields = ("author", "image_preview", "reading_time", "created_at", "updated_at")
    save_on_top = True
    list_per_page = 25

    def view_on_site(self, obj):
        if (
            obj.status == Post.Status.PUBLISHED
            and obj.published_at
            and obj.published_at <= timezone.now()
        ):
            return obj.get_absolute_url()
        return None

    actions = (
        "publish_posts",
        "back_to_draft",
        "archive_posts",
        "feature_posts",
        "unfeature_posts",
    )

    fieldsets = (
        (
            "Contenido",
            {
                "fields": ("title", "slug", "excerpt", "body", "reading_time"),
            },
        ),
        ("Imagen de portada", {"fields": ("cover_image", "image_preview")}),
        (
            "Publicación",
            {
                "fields": ("status", "published_at", "is_featured", "author"),
                "description": (
                    "El autor se asigna automáticamente a quien crea la noticia. "
                    "Si publicas sin indicar fecha, se usa el momento actual."
                ),
            },
        ),
        ("Registro", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Portada")
    def thumbnail(self, obj):
        return thumbnail_html(obj.cover_image)

    @admin.display(description="Vista previa")
    def image_preview(self, obj):
        return preview_html(obj.cover_image)

    @admin.display(description="Estado", ordering="status")
    def status_badge(self, obj):
        return badge(obj.get_status_display(), STATUS_TONES.get(obj.status, "neutral"))

    @admin.display(description="Tiempo de lectura")
    def reading_time(self, obj):
        words = len((obj.body or "").split())
        minutes = max(1, -(-words // WORDS_PER_MINUTE))  # division hacia arriba
        return f"{minutes} min · {words} palabras"

    def save_model(self, request, obj, form, change) -> None:
        if not change or obj.author_id is None:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Publicar noticias seleccionadas", permissions=["change"])
    def publish_posts(self, request, queryset) -> None:
        now = timezone.now()
        queryset.filter(published_at__isnull=True).update(published_at=now)
        updated = queryset.update(status=Post.Status.PUBLISHED, updated_at=now)
        self.message_user(
            request,
            f"{count_message(updated, 'noticia publicada', 'noticias publicadas')}.",
            messages.SUCCESS,
        )

    @admin.action(description="Regresar a borrador", permissions=["change"])
    def back_to_draft(self, request, queryset) -> None:
        updated = queryset.update(status=Post.Status.DRAFT, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'noticia regresó', 'noticias regresaron')} a borrador.",
            messages.WARNING,
        )

    @admin.action(description="Archivar noticias seleccionadas", permissions=["change"])
    def archive_posts(self, request, queryset) -> None:
        updated = queryset.update(status=Post.Status.ARCHIVED, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'noticia archivada', 'noticias archivadas')}.",
            messages.INFO,
        )

    @admin.action(description="Marcar como destacadas", permissions=["change"])
    def feature_posts(self, request, queryset) -> None:
        updated = queryset.update(is_featured=True, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'noticia destacada', 'noticias destacadas')}.",
            messages.SUCCESS,
        )

    @admin.action(description="Quitar de destacadas", permissions=["change"])
    def unfeature_posts(self, request, queryset) -> None:
        updated = queryset.update(is_featured=False, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'noticia ya no destacada', 'noticias ya no destacadas')}.",
            messages.INFO,
        )
