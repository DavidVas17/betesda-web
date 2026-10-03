from django.contrib import admin
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry

from .utils import badge

ACTION_TONES = {
    ADDITION: ("Creó", "ok"),
    CHANGE: ("Modificó", "info"),
    DELETION: ("Eliminó", "danger"),
}


@admin.register(LogEntry)
class ActivityLogAdmin(admin.ModelAdmin):
    """Bitácora de actividad de solo lectura: quién hizo qué y cuándo."""

    list_display = ("action_time", "user", "action_badge", "content_type", "object_repr")
    list_filter = ("action_flag", "content_type", "user")
    search_fields = ("object_repr", "change_message", "user__username")
    date_hierarchy = "action_time"
    list_select_related = ("user", "content_type")
    list_per_page = 50
    ordering = ("-action_time",)

    @admin.display(description="Acción", ordering="action_flag")
    def action_badge(self, obj):
        label, tone = ACTION_TONES.get(obj.action_flag, ("—", "neutral"))
        return badge(label, tone)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
