from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ContactMessageForm
from .models import ContactMessage
from .modes import CONTACT_MODES


def _contact(request):
    kind = (
        ContactMessage.Kind.CONTACT
        if request.GET.get("tipo") == "contacto"
        else ContactMessage.Kind.PRAYER
    )
    form = ContactMessageForm(request.POST if request.method == "POST" else None, kind=kind)
    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.source_ip = request.META.get("REMOTE_ADDR") or None
        message.save()
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
        },
    )


@require_http_methods(["GET", "POST"])
def contact(request):
    return _contact(request)


@require_POST
def send_message(request):
    return _contact(request)
