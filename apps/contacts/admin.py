from urllib.parse import quote

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import format_html

from apps.backoffice.utils import CsvExportMixin, badge, count_message

from .models import ContactMessage

STATUS_TONES = {
    ContactMessage.Status.NEW: "danger",
    ContactMessage.Status.IN_PROGRESS: "warn",
    ContactMessage.Status.CLOSED: "ok",
    ContactMessage.Status.SPAM: "neutral",
}
STALE_HOURS = 48


@admin.register(ContactMessage)
class ContactMessageAdmin(CsvExportMixin, admin.ModelAdmin):
    list_display = (
        "subject",
        "kind",
        "name",
        "email",
        "phone",
        "status_badge",
        "assigned_to",
        "waiting",
        "created_at",
    )
    list_display_links = ("subject",)
    list_filter = ("kind", "status", "assigned_to", "created_at")
    list_select_related = ("assigned_to",)
    search_fields = ("name", "email", "phone", "subject", "message", "internal_notes")
    date_hierarchy = "created_at"
    save_on_top = True
    list_per_page = 30
    readonly_fields = (
        "kind",
        "name",
        "reply_link",
        "phone",
        "subject",
        "message",
        "privacy_accepted",
        "source_ip",
        "created_at",
        "updated_at",
    )
    actions = (
        "mark_in_progress",
        "mark_closed",
        "mark_spam",
        "assign_to_me",
        "export_csv",
    )
    csv_fields = ("created_at", "kind", "name", "email", "phone", "subject", "status", "message")
    csv_filename = "mensajes-contacto"

    fieldsets = (
        (
            "Mensaje recibido",
            {"fields": ("kind", "name", "reply_link", "phone", "subject", "message", "created_at")},
        ),
        (
            "Seguimiento",
            {
                "fields": ("status", "assigned_to", "internal_notes"),
                "description": (
                    "Las notas internas son solo para el equipo; no se muestran a quien escribió."
                ),
            },
        ),
        (
            "Datos técnicos",
            {
                "fields": ("privacy_accepted", "source_ip", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request) -> bool:
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            kwargs["queryset"] = get_user_model().objects.filter(is_staff=True, is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # --- Columnas -------------------------------------------------------------
    @admin.display(description="Estado", ordering="status")
    def status_badge(self, obj):
        return badge(obj.get_status_display(), STATUS_TONES.get(obj.status, "neutral"))

    @admin.display(description="Espera", ordering="created_at")
    def waiting(self, obj):
        if obj.status != ContactMessage.Status.NEW:
            return "—"
        hours = (timezone.now() - obj.created_at).total_seconds() / 3600
        text = f"{int(hours // 24)} d {int(hours % 24)} h" if hours >= 24 else f"{int(hours)} h"
        return badge(text, "danger" if hours >= STALE_HOURS else "warn")

    @admin.display(description="Correo electrónico")
    def reply_link(self, obj):
        subject = quote(f"Re: {obj.subject}")
        return format_html(
            '<a href="mailto:{}?subject={}">{}</a> &mdash; <small>clic para responder</small>',
            obj.email,
            subject,
            obj.email,
        )

    # --- Guardado: quien atiende primero queda como responsable ---------------
    def save_model(self, request, obj, form, change) -> None:
        if (
            change
            and obj.assigned_to_id is None
            and obj.status != ContactMessage.Status.NEW
            and "status" in form.changed_data
        ):
            obj.assigned_to = request.user
        super().save_model(request, obj, form, change)

    # --- Acciones ---------------------------------------------------------------
    def _set_status(self, request, queryset, status, singular, plural, level) -> None:
        # Primero el responsable: el queryset puede estar filtrado por estado y, tras
        # cambiarlo, dejaria de incluir estos mensajes.
        if status != ContactMessage.Status.NEW:
            queryset.filter(assigned_to__isnull=True).update(assigned_to=request.user)
        updated = queryset.update(status=status, updated_at=timezone.now())
        self.message_user(request, f"{count_message(updated, singular, plural)}.", level)

    @admin.action(description="Marcar como «En seguimiento»", permissions=["change"])
    def mark_in_progress(self, request, queryset) -> None:
        self._set_status(
            request,
            queryset,
            ContactMessage.Status.IN_PROGRESS,
            "mensaje en seguimiento",
            "mensajes en seguimiento",
            messages.SUCCESS,
        )

    @admin.action(description="Marcar como «Cerrado»", permissions=["change"])
    def mark_closed(self, request, queryset) -> None:
        self._set_status(
            request,
            queryset,
            ContactMessage.Status.CLOSED,
            "mensaje cerrado",
            "mensajes cerrados",
            messages.SUCCESS,
        )

    @admin.action(description="Marcar como «No deseado»", permissions=["change"])
    def mark_spam(self, request, queryset) -> None:
        self._set_status(
            request,
            queryset,
            ContactMessage.Status.SPAM,
            "mensaje marcado como no deseado",
            "mensajes marcados como no deseados",
            messages.WARNING,
        )

    @admin.action(description="Asignarme los mensajes seleccionados", permissions=["change"])
    def assign_to_me(self, request, queryset) -> None:
        updated = queryset.update(assigned_to=request.user, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'mensaje asignado', 'mensajes asignados')} a ti.",
            messages.SUCCESS,
        )
