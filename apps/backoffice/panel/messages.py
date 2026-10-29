import csv
import logging

from django.contrib import messages
from django.contrib.admin.models import DELETION
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.alerts import alert_messages_exported
from apps.contacts import replies
from apps.contacts.models import ContactMessage

from .access import panel_required
from .forms import MessageFollowupForm, MessageReplyForm
from .security import recent_auth_required
from .utils import audit, paginate, pagination_query, panel_render

logger = logging.getLogger(__name__)


def _filtered(request):
    queryset = ContactMessage.objects.select_related("assigned_to").order_by("-created_at", "-pk")
    query = request.GET.get("q", "").strip()[:200]
    status = request.GET.get("status", request.GET.get("estado", "all"))
    kind = request.GET.get("kind", request.GET.get("tipo", "all"))
    if status not in ContactMessage.Status.values:
        status = "all"
    if kind not in ContactMessage.Kind.values:
        kind = "all"
    if status != "all":
        queryset = queryset.filter(status=status)
    if kind != "all":
        queryset = queryset.filter(kind=kind)
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(subject__icontains=query)
            | Q(message__icontains=query)
        )
    return queryset, query, status, kind


@panel_required("contacts.view_contactmessage")
@require_GET
def message_list(request):
    queryset, query, status, kind = _filtered(request)
    counts = ContactMessage.objects.aggregate(
        total=Count("pk"),
        new=Count("pk", filter=Q(status=ContactMessage.Status.NEW)),
        in_progress=Count("pk", filter=Q(status=ContactMessage.Status.IN_PROGRESS)),
        closed=Count("pk", filter=Q(status=ContactMessage.Status.CLOSED)),
    )
    return panel_render(
        request,
        "panel/messages.html",
        {
            "page_obj": paginate(request, queryset, 15),
            "query": query,
            "status": status,
            "kind": kind,
            "status_choices": (("all", "Todos los estados"), *ContactMessage.Status.choices),
            "kind_choices": (("all", "Todas las solicitudes"), *ContactMessage.Kind.choices),
            "can_change": request.user.has_perm("contacts.change_contactmessage"),
            "can_delete": request.user.has_perm("contacts.delete_contactmessage"),
            "can_export": request.user.has_perm("contacts.export_contactmessage"),
            "counts": counts,
            "pagination_query": pagination_query(request),
            "export_url": reverse("panel:message_export") + "?" + request.GET.urlencode(),
        },
        active="messages",
        title="Mensajes",
        subtitle="Contacto y peticiones de oración, en un mismo lugar.",
    )


@sensitive_post_parameters("internal_notes")
@panel_required("contacts.view_contactmessage")
@require_http_methods(["GET", "POST"])
def message_detail(request, pk):
    can_change = request.user.has_perm("contacts.change_contactmessage")
    if request.method == "POST" and not can_change:
        raise PermissionDenied
    # Lock the current workflow while saving, so two operators cannot overwrite a quick action.
    with transaction.atomic():
        queryset = (
            ContactMessage.objects.select_for_update(of=("self",))
            if request.method == "POST"
            else ContactMessage.objects
        )
        item = get_object_or_404(queryset.select_related("assigned_to"), pk=pk)
        form = MessageFollowupForm(
            request.POST if request.method == "POST" else None, instance=item
        )
        if request.method == "POST" and form.is_valid():
            item = form.save(commit=False)
            if item.status != ContactMessage.Status.NEW and not item.assigned_to_id:
                item.assigned_to = request.user
            item.save(update_fields=("status", "assigned_to", "internal_notes", "updated_at"))
            audit(request, item, message="Seguimiento de solicitud actualizado.")
            messages.success(
                request, "Seguimiento guardado. Las notas son privadas para el equipo."
            )
            return redirect("panel:message_detail", pk=item.pk)
    if not can_change:
        for field in form.fields.values():
            field.disabled = True
    phone = "".join(char for char in item.phone if char.isdigit())
    if len(phone) == 8:
        phone = "502" + phone
    return panel_render(
        request,
        "panel/message_detail.html",
        {
            "message": item,
            "form": form,
            "can_change": can_change,
            "can_delete": request.user.has_perm("contacts.delete_contactmessage"),
            "reply_url": replies.mailto(item),
            "reply_options": replies.options(item, request.user, _reply_site(request)),
            "reply_form": _reply_form(request, item) if can_change else None,
            "reply_sender": replies.sender_address(),
            "sent_replies": item.replies.select_related("author"),
            "whatsapp_url": (
                f"https://wa.me/{replies.whatsapp_number(item.phone)}"
                if replies.whatsapp_number(item.phone)
                else ""
            ),
            "phone_url": f"tel:+{phone}" if phone else "",
        },
        active="messages",
        title="Detalle de solicitud",
        subtitle="Escucha, acompaña y registra el seguimiento.",
    )


def _reply_site(request):
    from apps.core.context_processors import public_site

    site = public_site(request)["site"]
    return {"url": request.build_absolute_uri(reverse("core:home")), "phone": site.get("phone")}


def _reply_form(request, item, data=None):
    template = replies.REPLIES_BY_KEY.get(request.GET.get("plantilla", ""))
    if template and item.kind not in template.kinds:
        template = None
    initial = {
        "subject": replies.default_subject(item),
        "body": replies.render(template, item, request.user, _reply_site(request))
        if template
        else "",
    }
    return MessageReplyForm(data, initial=initial)


@sensitive_post_parameters("body")
@panel_required("contacts.change_contactmessage")
@require_POST
def message_reply(request, pk):
    """Envía la respuesta desde el correo de la iglesia y la deja en el historial."""
    item = get_object_or_404(ContactMessage, pk=pk)
    form = _reply_form(request, item, request.POST)
    if form.is_valid():
        try:
            replies.send(
                item, request.user, form.cleaned_data["subject"], form.cleaned_data["body"]
            )
        except Exception:  # noqa: BLE001 - se informa en pantalla y no se guarda nada
            logger.exception("No se pudo enviar la respuesta a la solicitud #%s", item.pk)
            messages.error(
                request,
                "No se pudo enviar el correo. Revisa la configuración de correo del sitio o "
                "responde por WhatsApp.",
            )
        else:
            audit(request, item, message="Respuesta enviada por correo.")
            messages.success(request, f"Respuesta enviada a {item.email}.")
            return redirect(f"{reverse('panel:message_detail', args=[item.pk])}#respuestas")
    else:
        messages.error(request, "Escribe el asunto y el mensaje antes de enviar.")
    return redirect(f"{reverse('panel:message_detail', args=[item.pk])}#responder")


@panel_required("contacts.change_contactmessage")
@require_POST
def message_action(request, pk):
    if not request.user.has_perm("contacts.change_contactmessage"):
        raise PermissionDenied
    action = request.POST.get("action", "")
    states = {
        "new": ContactMessage.Status.NEW,
        "in_progress": ContactMessage.Status.IN_PROGRESS,
        "close": ContactMessage.Status.CLOSED,
        "spam": ContactMessage.Status.SPAM,
    }
    if action not in {*states, "assign"}:
        return HttpResponseBadRequest("La acción no es válida.")
    with transaction.atomic():
        item = get_object_or_404(ContactMessage.objects.select_for_update(), pk=pk)
        if action in states:
            item.status = states[action]
        if action == "assign" or (action != "new" and not item.assigned_to_id):
            item.assigned_to = request.user
        item.save(update_fields=("status", "assigned_to", "updated_at"))
        audit(request, item, message="Estado o responsable de solicitud actualizado.")
    messages.success(request, "Solicitud actualizada correctamente.")
    return redirect("panel:message_detail", pk=pk)


@panel_required("contacts.delete_contactmessage")
@recent_auth_required
@require_http_methods(["GET", "POST"])
def message_delete(request, pk):
    item = get_object_or_404(ContactMessage, pk=pk)
    if request.method == "POST":
        with transaction.atomic():
            audit(request, item, flag=DELETION, message="Solicitud eliminada.")
            item.delete()
        messages.success(request, "Solicitud eliminada.")
        return redirect("panel:message_list")
    return panel_render(
        request,
        "panel/delete.html",
        {
            "object": item,
            "object_label": "Solicitud",
            "cancel_url": reverse("panel:message_detail", args=[pk]),
            "delete_message": (
                "Se eliminarán el mensaje y las notas del equipo. Esta acción no se puede deshacer."
            ),
        },
        active="messages",
        title="Eliminar solicitud",
    )


def _csv_value(value):
    text = str(value) if value is not None else ""
    # Spreadsheet engines may ignore leading whitespace before interpreting a formula.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


@panel_required("contacts.export_contactmessage")
@recent_auth_required
@require_GET
def message_export(request):
    queryset, *_ = _filtered(request)
    total = queryset.count()
    audit(request, request.user, message=f"Exportar {total} solicitudes a CSV.")
    alert_messages_exported(request.user, total, request=request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="solicitudes-betesda.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        (
            "Fecha",
            "Tipo",
            "Nombre",
            "Correo",
            "Teléfono",
            "Asunto",
            "Mensaje",
            "Estado",
            "Responsable",
            "Notas internas",
        )
    )
    for item in queryset.iterator(chunk_size=500):
        writer.writerow(
            map(
                _csv_value,
                (
                    timezone.localtime(item.created_at).strftime("%Y-%m-%d %H:%M"),
                    item.get_kind_display(),
                    item.name,
                    item.email,
                    item.phone,
                    item.subject,
                    item.message,
                    item.get_status_display(),
                    item.assigned_to.get_full_name() or item.assigned_to.username
                    if item.assigned_to
                    else "",
                    item.internal_notes,
                ),
            )
        )
    return response
