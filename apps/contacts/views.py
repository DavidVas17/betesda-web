from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.schedule import schedule_context

from .forms import ContactMessageForm
from .models import ContactMessage
from .modes import CONTACT_MODES
from .notifications import notify_team
from .protection import client_ip, too_many_recent_messages

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
    if request.method == "POST" and form.is_valid() and too_many_recent_messages(ip):
        form.add_error(None, RATE_LIMIT_MESSAGE)
        status = 429
    elif request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.source_ip = ip
        message.save()
        # Después de confirmar el guardado: si el correo falla o tarda, la petición ya está a salvo.
        transaction.on_commit(lambda: notify_team(message, request))
        mode = CONTACT_MODES[message.kind]
        messages.success(request, mode["success"], extra_tags="contact")
        return redirect(f"{reverse('contacts:contact')}?tipo={mode['slug']}#formulario")

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
            "retention_months": max(1, round(settings.MESSAGE_RETENTION_DAYS / 30.4)),
            **schedule_context(),
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
def contact(request):
    return _contact(request)


@require_POST
def send_message(request):
    return _contact(request)
