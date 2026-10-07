from datetime import timedelta

from django.contrib import admin, messages
from django.utils import timezone

from apps.backoffice.utils import (
    CsvExportMixin,
    badge,
    count_message,
    preview_html,
    thumbnail_html,
)

from .models import Event


class EventTimingFilter(admin.SimpleListFilter):
    title = "momento"
    parameter_name = "when"

    def lookups(self, request, model_admin):
        return (
            ("upcoming", "Próximos"),
            ("week", "Esta semana"),
            ("past", "Ya realizados"),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "upcoming":
            return queryset.filter(starts_at__gte=now)
        if self.value() == "week":
            return queryset.filter(starts_at__gte=now, starts_at__lte=now + timedelta(days=7))
        if self.value() == "past":
            return queryset.filter(starts_at__lt=now)
        return queryset


@admin.register(Event)
class EventAdmin(CsvExportMixin, admin.ModelAdmin):
    list_display = (
        "thumbnail",
        "title",
        "starts_at",
        "location",
        "timing",
        "is_published",
        "is_featured",
    )
    list_display_links = ("title",)
    list_editable = ("is_published", "is_featured")
    list_filter = (EventTimingFilter, "is_published", "is_featured")
    search_fields = ("title", "summary", "description", "location")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "starts_at"
    readonly_fields = ("image_preview", "created_at", "updated_at")
    save_on_top = True
    list_per_page = 25

    def view_on_site(self, obj):
        return obj.get_absolute_url() if obj.is_published else None

    actions = (
        "publish_events",
        "unpublish_events",
        "feature_events",
        "unfeature_events",
        "duplicate_events",
        "export_csv",
    )
    csv_fields = ("title", "starts_at", "ends_at", "location", "is_published", "is_featured")
    csv_filename = "eventos"

    fieldsets = (
        ("Contenido", {"fields": ("title", "slug", "summary", "description")}),
        ("Fecha y lugar", {"fields": ("starts_at", "ends_at", "location")}),
        ("Imagen de portada", {"fields": ("cover_image", "image_preview")}),
        ("Publicación", {"fields": ("is_published", "is_featured")}),
        (
            "Registro",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Portada")
    def thumbnail(self, obj):
        return thumbnail_html(obj.cover_image)

    @admin.display(description="Vista previa")
    def image_preview(self, obj):
        return preview_html(obj.cover_image)

    @admin.display(description="Momento", ordering="starts_at")
    def timing(self, obj):
        now = timezone.now()
        end = obj.ends_at or obj.starts_at
        if end < now:
            return badge("Realizado", "neutral")
        if obj.starts_at <= now:
            return badge("En curso", "ok")
        if timezone.localdate(obj.starts_at) == timezone.localdate(now):
            return badge("Hoy", "warn")
        return badge("Próximo", "info")

    @admin.action(description="Publicar eventos seleccionados", permissions=["change"])
    def publish_events(self, request, queryset) -> None:
        updated = queryset.update(is_published=True, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'evento publicado', 'eventos publicados')}.",
            messages.SUCCESS,
        )

    @admin.action(description="Despublicar eventos seleccionados", permissions=["change"])
    def unpublish_events(self, request, queryset) -> None:
        updated = queryset.update(is_published=False, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'evento despublicado', 'eventos despublicados')}.",
            messages.WARNING,
        )

    @admin.action(description="Marcar como destacados", permissions=["change"])
    def feature_events(self, request, queryset) -> None:
        updated = queryset.update(is_featured=True, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'evento destacado', 'eventos destacados')}.",
            messages.SUCCESS,
        )

    @admin.action(description="Quitar de destacados", permissions=["change"])
    def unfeature_events(self, request, queryset) -> None:
        updated = queryset.update(is_featured=False, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'evento ya no destacado', 'eventos ya no destacados')}.",
            messages.INFO,
        )

    @admin.action(description="Duplicar como borrador", permissions=["add"])
    def duplicate_events(self, request, queryset) -> None:
        created = 0
        for event in queryset:
            Event.objects.create(
                title=f"{event.title[:165]} (copia)",
                summary=event.summary,
                description=event.description,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                location=event.location,
                cover_image=event.cover_image,
                is_published=False,
                is_featured=False,
            )
            created += 1
        self.message_user(
            request,
            f"{count_message(created, 'copia creada', 'copias creadas')} como borrador. "
            "Ajusta la fecha antes de publicar.",
            messages.SUCCESS,
        )
