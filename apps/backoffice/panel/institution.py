"""Ministerios y valores de la iglesia, editables desde el panel."""

from dataclasses import dataclass

from django import forms
from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.models import ChurchValue, Ministry, ServiceTime

from .access import panel_required, require_permission
from .form_layout import FieldsetsMixin
from .utils import audit, panel_render


class MinistryForm(FieldsetsMixin, forms.ModelForm):
    fieldsets = (
        ("Lo básico", "Cómo se llama y cómo se reconoce.", ("name", "tag", "icon")),
        ("Descripción", "Una o dos frases sobre lo que hace este ministerio.", ("description",)),
        ("En el sitio", "El orden menor aparece primero.", ("order", "is_active")),
    )

    class Meta:
        model = Ministry
        fields = ("name", "tag", "icon", "description", "order", "is_active")
        labels = {
            "name": "Nombre del ministerio",
            "tag": "Etiqueta corta",
            "icon": "Ícono",
            "description": "Descripción",
            "order": "Orden",
            "is_active": "Mostrar en el sitio",
        }
        help_texts = {
            "tag": "Aparece sobre el nombre, por ejemplo: Jóvenes.",
            "is_active": "Si lo apagas, el ministerio deja de verse sin perder su información.",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class ChurchValueForm(FieldsetsMixin, forms.ModelForm):
    fieldsets = (
        ("El valor", "Una palabra y una frase que lo explique.", ("name", "description")),
        ("En el sitio", "El orden menor aparece primero.", ("order", "is_active")),
    )

    class Meta:
        model = ChurchValue
        fields = ("name", "description", "order", "is_active")
        labels = {
            "name": "Valor",
            "description": "Descripción",
            "order": "Orden",
            "is_active": "Mostrar en el sitio",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class ServiceTimeForm(FieldsetsMixin, forms.ModelForm):
    fieldsets = (
        ("El culto", "Cómo se llama y algún detalle útil para quien visita.", ("name", "note")),
        (
            "Día y hora",
            "Hora local de Guatemala. Se repite cada semana.",
            (
                "day",
                "starts_at",
                "ends_at",
            ),
        ),
        ("En el sitio", "Apágalo si se suspende por un tiempo.", ("is_active",)),
    )

    class Meta:
        model = ServiceTime
        fields = ("name", "note", "day", "starts_at", "ends_at", "is_active")
        labels = {
            "name": "Nombre del culto o reunión",
            "note": "Detalle",
            "day": "Día",
            "starts_at": "Hora de inicio",
            "ends_at": "Hora de finalización",
            "is_active": "Mostrar en el sitio",
        }
        help_texts = {
            "name": "Por ejemplo: Culto general, Escuela dominical, Reunión de jóvenes.",
            "note": "Opcional. Por ejemplo: Para toda la familia.",
            "ends_at": "Déjala vacía si no hay hora fija de finalización.",
        }
        widgets = {
            "starts_at": forms.TimeInput(format="%H:%M", attrs={"type": "time", "data-starts": ""}),
            "ends_at": forms.TimeInput(format="%H:%M", attrs={"type": "time", "data-ends": ""}),
        }


def _describe_service(item):
    return item.get_day_display()[:3], f"{item.name} · {item.time_label} h", item.note


def _describe_ministry(item):
    return item.order, item.name, f"{item.tag} · {item.description}"


def _describe_value(item):
    return item.order, item.name, item.description


@dataclass(frozen=True)
class Section:
    model: type
    form: type
    key: str
    singular: str
    plural: str
    article: str
    describe: object
    hint: str

    def perm(self, action: str) -> str:
        return f"core.{action}_{self.model._meta.model_name}"


SECTIONS = {
    "horarios": Section(
        ServiceTime,
        ServiceTimeForm,
        "horarios",
        "horario",
        "Horarios de culto",
        "el",
        _describe_service,
        "Se muestran en Inicio, con el próximo culto destacado, y en Contacto.",
    ),
    "ministerios": Section(
        Ministry,
        MinistryForm,
        "ministerios",
        "ministerio",
        "Ministerios",
        "el",
        _describe_ministry,
        "Se muestran en Inicio (los tres primeros) y en la página Ministerios.",
    ),
    "valores": Section(
        ChurchValue,
        ChurchValueForm,
        "valores",
        "valor",
        "Valores",
        "el",
        _describe_value,
        "Se muestran en la página Nosotros.",
    ),
}


def _section(kind: str) -> Section:
    try:
        return SECTIONS[kind]
    except KeyError as error:
        from django.http import Http404

        raise Http404 from error


@panel_required(("core.view_ministry", "core.view_churchvalue", "core.view_servicetime"))
@require_GET
def overview(request):
    user = request.user
    groups = []
    for section in SECTIONS.values():
        if not user.has_perm(section.perm("view")):
            continue
        items = list(section.model.objects.all())
        for item in items:
            item.edit_url = reverse("panel:institution_edit", args=[section.key, item.pk])
            item.badge, item.title, item.subtitle = section.describe(item)
        groups.append(
            {
                "section": section,
                "items": items,
                "create_url": reverse("panel:institution_create", args=[section.key])
                if user.has_perm(section.perm("add"))
                else "",
            }
        )
    return panel_render(
        request,
        "panel/institution.html",
        {"groups": groups},
        active="institution",
        title="Nuestra iglesia",
        subtitle="Horarios, ministerios y valores que se muestran en el sitio.",
    )


def _form_view(request, kind, pk=None):
    section = _section(kind)
    obj = get_object_or_404(section.model, pk=pk) if pk is not None else None
    action = "change" if obj else "add"
    require_permission(request, section.perm(action if request.method == "POST" else "view"))
    can_save = request.user.has_perm(section.perm(action))
    form = section.form(request.POST if request.method == "POST" else None, instance=obj)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            audit(
                request,
                saved,
                flag=CHANGE if obj else ADDITION,
                message=f"{section.singular.capitalize()} {'actualizado' if obj else 'creado'}.",
            )
        messages.success(request, f"Se guardó {section.article} {section.singular}.")
        return redirect("panel:institution")
    if not can_save:
        for field in form.fields.values():
            field.disabled = True
    title = f"{'Editar' if obj else 'Agregar'} {section.singular}"
    return panel_render(
        request,
        "panel/form.html",
        {
            "form": form,
            "form_title": title,
            "form_intro": "Los cambios se ven en el sitio al guardar.",
            "form_help": "Escribe con palabras sencillas: así lo entiende quien visita el sitio "
            "por primera vez.",
            "cancel_url": reverse("panel:institution"),
            "submit_label": "Guardar",
            "can_save": can_save,
            "object": obj,
            "delete_url": reverse("panel:institution_delete", args=[kind, obj.pk])
            if obj and request.user.has_perm(section.perm("delete"))
            else "",
        },
        active="institution",
        title=title,
    )


@panel_required(("core.add_ministry", "core.add_churchvalue", "core.add_servicetime"))
@require_http_methods(["GET", "POST"])
def create(request, kind):
    return _form_view(request, kind)


@panel_required(("core.view_ministry", "core.view_churchvalue", "core.view_servicetime"))
@require_http_methods(["GET", "POST"])
def edit(request, kind, pk):
    return _form_view(request, kind, pk)


@panel_required(("core.delete_ministry", "core.delete_churchvalue", "core.delete_servicetime"))
@require_http_methods(["GET", "POST"])
def delete(request, kind, pk):
    section = _section(kind)
    require_permission(request, section.perm("delete"))
    obj = get_object_or_404(section.model, pk=pk)
    if request.method == "POST":
        with transaction.atomic():
            audit(
                request, obj, flag=DELETION, message=f"{section.singular.capitalize()} eliminado."
            )
            obj.delete()
        messages.success(request, f"Se eliminó {section.article} {section.singular}.")
        return redirect("panel:institution")
    return panel_render(
        request,
        "panel/delete.html",
        {
            "object": obj,
            "object_label": f"{section.article} {section.singular}",
            "cancel_url": reverse("panel:institution_edit", args=[kind, pk]),
            "delete_message": "Dejará de aparecer en el sitio. Si solo quieres ocultarlo por un "
            "tiempo, apaga «Mostrar en el sitio».",
        },
        active="institution",
        title=f"Eliminar {section.singular}",
    )
