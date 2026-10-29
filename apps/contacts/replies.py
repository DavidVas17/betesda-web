"""Respuestas a peticiones y mensajes.

Se envían desde el panel con el correo de la iglesia (el que define ``DEFAULT_FROM_EMAIL``,
por ejemplo el Gmail de la iglesia) y con el diseño del sitio. Nadie del equipo necesita la
contraseña de ese correo, y cada respuesta queda en el historial de la solicitud. Si la
persona contesta, su respuesta llega al buzón de la iglesia.

Las respuestas listas son un punto de partida: se editan antes de enviar. WhatsApp queda como
alternativa y se abre con el mismo texto.
"""

import re
from dataclasses import dataclass
from email.utils import parseaddr
from urllib.parse import quote, urlencode

from django.conf import settings
from django.db import transaction

from apps.core.emails import Email

from .models import ContactMessage, MessageReply


@dataclass(frozen=True)
class Reply:
    key: str
    label: str
    kinds: tuple[str, ...]
    body: str


PRAYER = ContactMessage.Kind.PRAYER
CONTACT = ContactMessage.Kind.CONTACT

REPLIES = (
    Reply(
        key="oracion",
        label="Estamos orando por ti",
        kinds=(PRAYER,),
        body=(
            "Hola {nombre}:\n\n"
            "Gracias por confiarnos tu petición. Queremos que sepas que no estás pasando por "
            "esto sin compañía: desde hoy la estamos presentando a Dios en oración como equipo."
            "\n\n«Echa sobre el Señor tu carga, y él te sustentará» (Salmo 55:22).\n\n"
            "Si quieres conversar, recibir una visita u orar con alguien en persona, responde "
            "a este correo y con gusto te acompañamos.\n\n"
            "Con cariño y en oración,\n{firma}"
        ),
    ),
    Reply(
        key="acompanar",
        label="Queremos acompañarte",
        kinds=(PRAYER,),
        body=(
            "Hola {nombre}:\n\n"
            "Leímos tu petición y nos gustaría acompañarte de una forma más cercana. Si te "
            "parece bien, podemos llamarte, visitarte o reunirnos contigo en la iglesia para "
            "orar juntos.\n\n"
            "Respóndenos con el día y la hora que mejor te queden, o con un número de teléfono "
            "si prefieres que te llamemos.\n\n"
            "Seguimos orando por ti,\n{firma}"
        ),
    ),
    Reply(
        key="gracias",
        label="Gracias por escribir",
        kinds=(CONTACT,),
        body=(
            "Hola {nombre}:\n\n"
            "Gracias por escribirnos. Recibimos tu mensaje sobre «{asunto}» y ya lo estamos "
            "revisando.\n\n"
            "Te responderemos con más detalle muy pronto.{urgente}\n\n"
            "Saludos cordiales,\n{firma}"
        ),
    ),
    Reply(
        key="visita",
        label="Te invitamos a visitarnos",
        kinds=(PRAYER, CONTACT),
        body=(
            "Hola {nombre}:\n\n"
            "Nos encantaría conocerte en persona. Te esperamos en nuestras reuniones; aquí "
            "puedes ver los horarios y cómo llegar: {sitio}\n\n"
            "Si es tu primera vez, búscanos al llegar: con gusto te recibimos y te presentamos "
            "a la familia de la iglesia.\n\n"
            "¡Bendiciones!\n{firma}"
        ),
    ),
    Reply(
        key="detalles",
        label="Pedir más detalles",
        kinds=(PRAYER, CONTACT),
        body=(
            "Hola {nombre}:\n\n"
            "Gracias por tu mensaje. Para ayudarte mejor, ¿nos podrías contar un poco más sobre "
            "lo que necesitas? Cualquier detalle nos sirve para darte una respuesta más "
            "precisa.\n\n"
            "Quedamos atentos,\n{firma}"
        ),
    ),
)
REPLIES_BY_KEY = {reply.key: reply for reply in REPLIES}


def _first_name(full_name: str) -> str:
    parts = (full_name or "").split()
    return parts[0] if parts else ""


def signature(actor) -> str:
    name = actor.get_full_name() or actor.get_username()
    return f"{name}\nBetesda Rosa de Sarón"


def available(message: ContactMessage) -> list[Reply]:
    return [reply for reply in REPLIES if message.kind in reply.kinds]


def render(reply: Reply, message: ContactMessage, actor, site: dict) -> str:
    phone = site.get("phone", "")
    return reply.body.format(
        nombre=_first_name(message.name) or "hermano",
        asunto=message.subject,
        firma=signature(actor),
        sitio=site.get("url", ""),
        urgente=f" Si es algo urgente, también puedes llamarnos al {phone}." if phone else "",
    )


def default_subject(message: ContactMessage) -> str:
    return f"Re: {message.subject}"[:200]


# --- Enlaces externos (WhatsApp, correo propio) ---------------------------------------------------


def mailto(message: ContactMessage, body: str = "") -> str:
    query = {"subject": default_subject(message)}
    if body:
        query["body"] = body
    # Los clientes de correo esperan %20 y no "+" para los espacios.
    return f"mailto:{quote(message.email, safe='@')}?{urlencode(query, quote_via=quote)}"


def whatsapp_number(phone: str) -> str:
    digits = "".join(ch for ch in phone or "" if ch.isdigit())
    if len(digits) == 8:  # número de Guatemala sin código de país
        digits = "502" + digits
    return digits if 10 <= len(digits) <= 15 else ""


def whatsapp_url(message: ContactMessage, body: str) -> str:
    number = whatsapp_number(message.phone)
    if not number:
        return ""
    return f"https://wa.me/{number}?{urlencode({'text': body}, quote_via=quote)}"


def options(message: ContactMessage, actor, site: dict) -> list[dict]:
    result = []
    for reply in available(message):
        body = render(reply, message, actor, site)
        result.append(
            {"key": reply.key, "label": reply.label, "whatsapp_url": whatsapp_url(message, body)}
        )
    return result


# --- Envío desde el panel -----------------------------------------------------------------------


def sender_address() -> str:
    return parseaddr(settings.DEFAULT_FROM_EMAIL)[1]


def _paragraphs(body: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", body.strip()) if part.strip()]


def build_email(message: ContactMessage, subject: str, body: str) -> Email:
    is_prayer = message.kind == PRAYER
    paragraphs = _paragraphs(body)
    return Email(
        subject=subject,
        eyebrow="Betesda Rosa de Sarón",
        title="Sobre tu petición de oración" if is_prayer else "Sobre tu mensaje",
        paragraphs=paragraphs,
        preheader=paragraphs[1] if len(paragraphs) > 1 else "",
        footer=(
            "Puedes responder directamente a este correo. Recibiste este mensaje porque "
            "escribiste a la iglesia desde nuestro sitio web."
        ),
    )


def send(message: ContactMessage, actor, subject: str, body: str) -> MessageReply:
    """Envía la respuesta y la guarda en el historial. Si el correo falla, no se guarda nada
    y el error sube para que el panel lo muestre."""
    email = build_email(message, subject, body).message(to=[message.email])
    if settings.CONTACT_NOTIFY_EMAILS:
        email.reply_to = list(settings.CONTACT_NOTIFY_EMAILS[:1])
    email.send()
    with transaction.atomic():
        reply = MessageReply.objects.create(
            message=message, author=actor, subject=subject, body=body
        )
        changed = ["updated_at"]
        if message.status == ContactMessage.Status.NEW:
            message.status = ContactMessage.Status.IN_PROGRESS
            changed.append("status")
        if not message.assigned_to_id:
            message.assigned_to = actor
            changed.append("assigned_to")
        message.save(update_fields=changed)
    return reply
