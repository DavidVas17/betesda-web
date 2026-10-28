import logging

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.schedule import schedule_context

from . import turnstile
from .forms import ContactMessageForm
from .models import ContactMessage
from .modes import CONTACT_MODES
from .notifications import notify_team
from .protection import client_ip, too_many_recent_messages
from .spam import is_duplicate, spam_reasons, too_many_from_email

TURNSTILE_MESSAGE = (
    "No pudimos confirmar que eres una persona. Espera a que aparezca la marca de verificación "
    "y vuelve a enviar."
)
logger = logging.getLogger(__name__)

RATE_LIMIT_MESSAGE = (
    "Recibimos varios mensajes desde tu conexión en poco tiempo. "
    "Espera unos minutos e inténtalo de nuevo, o llámanos por teléfono."
)


def _contact(request):
    kind = (
        ContactMessage.Kind.CONTACT
        if request.GET.get("tipo") == "contacto"
        else ContactMessage.Kind.PRAYER
    )
    form = ContactMessageForm(request.POST if request.method == "POST" else None, kind=kind)
    status = 200
    ip = client_ip(request) if request.method == "POST" else None
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        mode = CONTACT_MODES[data["kind"]]
        if form.bot_reason:
            # A un bot se le responde igual que a una persona: así no aprende la trampa.
            logger.info("Envío descartado (%s) desde %s", form.bot_reason, ip)
            return _sent(request, mode)
        if not turnstile.verify(request.POST.get(turnstile.FIELD, ""), ip):
            form.add_error(None, TURNSTILE_MESSAGE)
            status = 400
        elif too_many_recent_messages(ip) or too_many_from_email(data["email"]):
            form.add_error(None, RATE_LIMIT_MESSAGE)
            status = 429
        elif is_duplicate(data["email"], data["message"]):
            return _sent(request, mode)  # ya lo teníamos: no se duplica ni se avisa otra vez
        else:
            message = form.save(commit=False)
            message.source_ip = ip
            reasons = spam_reasons(
                name=message.name, subject=message.subject, message=message.message
            )
            if reasons:
                message.status = ContactMessage.Status.SPAM
                message.internal_notes = "Marcado como no deseado automáticamente: " + "; ".join(
                    reasons
                )
            message.save()
            if not reasons:
                # Tras confirmar el guardado: si el correo falla, la petición ya está a salvo.
                transaction.on_commit(lambda: notify_team(message, request))
            return _sent(request, mode)

    return render(
        request,
        "contacts/contact.html",
        {
            "contact_form": form,
            "contact_mode": form.mode,
            "contact_modes": list(CONTACT_MODES.values()),
            "contact_config": {
                kind: {key: value for key, value in mode.items() if key != "success"}
                for kind, mode in CONTACT_MODES.items()
            },
            "turnstile_site_key": settings.TURNSTILE_SITE_KEY if turnstile.enabled() else "",
            "turnstile_script": turnstile.SCRIPT_URL,
            "retention_months": max(1, round(settings.MESSAGE_RETENTION_DAYS / 30.4)),
            **schedule_context(),
        },
        status=status,
    )


def _sent(request, mode):
    messages.success(request, mode["success"], extra_tags="contact")
    return redirect(f"{reverse('contacts:contact')}?tipo={mode['slug']}#formulario")


@require_http_methods(["GET", "POST"])
def contact(request):
    return _contact(request)


@require_POST
def send_message(request):
    return _contact(request)
