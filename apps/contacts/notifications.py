"""Aviso por correo al equipo cuando llega una petición de oración o un mensaje.

El correo no incluye el contenido de la solicitud: es información personal y a veces
delicada. Solo avisa que llegó y enlaza al panel, donde se lee con la sesión iniciada.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.mail import EmailMessage
from django.db.models import Q
from django.urls import reverse

from .models import ContactMessage

logger = logging.getLogger(__name__)


def recipients() -> list[str]:
    """Correos de quienes pueden leer mensajes y no apagaron los avisos, más el buzón de la
    iglesia (``CONTACT_NOTIFY_EMAILS``), que siempre recibe el aviso."""
    readers = Permission.objects.filter(
        content_type__app_label="contacts", codename="view_contactmessage"
    )
    users = (
        get_user_model()
        .objects.filter(is_active=True, is_staff=True, notify_new_messages=True)
        .exclude(email="")
        .filter(
            Q(is_superuser=True)
            | Q(groups__permissions__in=readers)
            | Q(user_permissions__in=readers)
        )
        .distinct()
    )
    shared = {email.strip() for email in settings.CONTACT_NOTIFY_EMAILS if email.strip()}
    return sorted({user.email for user in users} | shared)


def notify_team(message: ContactMessage, request) -> int:
    """Envía el aviso. Devuelve cuántas personas lo recibieron; nunca interrumpe el envío."""
    emails = recipients()
    if not emails:
        return 0
    is_prayer = message.kind == ContactMessage.Kind.PRAYER
    what = "una nueva petición de oración" if is_prayer else "un nuevo mensaje de contacto"
    subject = "Nueva petición de oración" if is_prayer else "Nuevo mensaje de contacto"
    detail_url = request.build_absolute_uri(reverse("panel:message_detail", args=[message.pk]))
    account_url = request.build_absolute_uri(reverse("panel:account"))
    body = (
        f"Hola:\n\n"
        f"Recibimos {what} en el sitio de la iglesia (solicitud #{message.pk}).\n\n"
        f"Ábrela en el panel para leerla y darle seguimiento:\n{detail_url}\n\n"
        f"Por privacidad, este correo no incluye el contenido ni los datos de la persona.\n\n"
        f"—\nRecibes este aviso porque atiendes los mensajes del sitio. "
        f"Puedes apagarlo en Mi cuenta: {account_url}\n"
    )
    email = EmailMessage(
        subject=f"[Betesda] {subject}",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[],
        bcc=emails,  # nadie ve los correos del resto del equipo
    )
    try:
        email.send()
    except Exception:  # noqa: BLE001 - un fallo de correo no debe perder la petición
        logger.exception("No se pudo enviar el aviso de la solicitud #%s", message.pk)
        return 0
    return len(emails)
