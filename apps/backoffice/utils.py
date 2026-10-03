import csv
from collections.abc import Iterable
from datetime import date, datetime

from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

CSV_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def badge(text: str, tone: str = "neutral"):
    """Etiqueta de color reutilizable en listados."""
    return format_html('<span class="bo-badge bo-badge--{}">{}</span>', tone, text)


def thumbnail_html(image_field, size: int = 44):
    """Miniatura de un ImageField para listados; guion si no hay imagen."""
    if not image_field:
        return mark_safe('<span class="bo-muted">&mdash;</span>')
    return format_html(
        '<img src="{}" alt="" class="bo-thumb" style="width:{}px;height:{}px" loading="lazy">',
        image_field.url,
        size,
        size,
    )


def preview_html(image_field):
    """Vista previa grande para formularios de edición."""
    if not image_field:
        return mark_safe('<span class="bo-muted">Aún no se ha cargado una imagen.</span>')
    return format_html('<img src="{}" alt="" class="bo-preview">', image_field.url)


def count_message(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _safe_cell(value) -> str:
    """Neutraliza fórmulas para evitar inyección CSV al abrir el archivo en Excel."""
    text = "" if value is None else str(value)
    if text.startswith(CSV_DANGEROUS_PREFIXES):
        return "'" + text
    return text


class CsvExportMixin:
    """Agrega la acción ``Exportar seleccionados a CSV``.

    La acción queda disponible para cualquier usuario del BackOffice que tenga permiso de
    lectura sobre el modelo, igual que el resto de herramientas operativas del panel.
    """

    csv_fields: Iterable[str] = ()
    csv_filename = "exportacion"

    @admin.action(permissions=["view"], description="Exportar seleccionados a CSV")
    def export_csv(self, request, queryset):
        fields = [self.model._meta.get_field(name) for name in self.csv_fields]
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{self.csv_filename}-{stamp}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow([str(field.verbose_name).capitalize() for field in fields])
        for obj in queryset:
            row = []
            for field in fields:
                value = getattr(obj, f"get_{field.name}_display", None)
                value = value() if callable(value) else getattr(obj, field.name)
                if isinstance(value, datetime):
                    if timezone.is_aware(value):
                        value = timezone.localtime(value)
                    value = value.strftime("%Y-%m-%d %H:%M")
                elif isinstance(value, date):
                    value = value.strftime("%Y-%m-%d")
                row.append(_safe_cell(value))
            writer.writerow(row)
        return response
