"""Respuestas listas para el equipo. Se abren en el correo (o WhatsApp) de quien responde,
ya con el texto, para personalizarlas antes de enviar: el sitio nunca envía en su nombre."""

from dataclasses import dataclass
from urllib.parse import quote, urlencode

from .models import ContactMessage


@dataclass(frozen=True)
class Reply:
    key: str
    label: str
    kinds: tuple[str, ...]
    body: str


REPLIES = (
    Reply(
        key="oracion",
        label="Estamos orando por ti",
        kinds=(ContactMessage.Kind.PRAYER,),
        body=(
            "Hola {nombre}:\n\n"
            "Recibimos tu petición y queremos que sepas que no estás solo(a). Como equipo "
            "estamos orando por ti y por lo que nos compartiste.\n\n"
            "«Echa sobre el Señor tu carga, y él te sustentará» (Salmo 55:22).\n\n"
            "Si quieres conversar o que alguien te visite, responde a este mensaje y con gusto "
            "te acompañamos.\n\n"
            "Con cariño,\n{firma}"
        ),
    ),
    Reply(
        key="gracias",
        label="Gracias por escribir",
        kinds=(ContactMessage.Kind.CONTACT,),
        body=(
            "Hola {nombre}:\n\n"
            "Gracias por escribirnos. Recibimos tu mensaje sobre «{asunto}» y ya lo estamos "
            "revisando.\n\n"
            "Te responderemos con más detalle muy pronto.\n\n"
            "Saludos,\n{firma}"
        ),
    ),
    Reply(
        key="visita",
        label="Te invitamos a visitarnos",
        kinds=(ContactMessage.Kind.PRAYER, ContactMessage.Kind.CONTACT),
        body=(
            "Hola {nombre}:\n\n"
            "Nos encantaría conocerte en persona. Te esperamos en nuestros cultos; puedes ver "
            "los horarios y cómo llegar aquí: {sitio}\n\n"
            "Si es tu primera vez, búscanos al llegar y con gusto te recibimos.\n\n"
            "Bendiciones,\n{firma}"
        ),
    ),
    Reply(
        key="detalles",
        label="Pedir más detalles",
        kinds=(ContactMessage.Kind.PRAYER, ContactMessage.Kind.CONTACT),
        body=(
            "Hola {nombre}:\n\n"
            "Gracias por escribirnos. Para poder ayudarte mejor, ¿nos podrías contar un poco "
            "más sobre lo que necesitas?\n\n"
            "Quedamos atentos.\n{firma}"
        ),
    ),
)


def _first_name(full_name: str) -> str:
    return (full_name or "").split()[0] if (full_name or "").split() else ""


def _signature(actor) -> str:
    name = actor.get_full_name() or actor.get_username()
    return f"{name}\nBetesda Rosa de Sarón"


def render(reply: Reply, message: ContactMessage, actor, site_url: str) -> str:
    return reply.body.format(
        nombre=_first_name(message.name) or "hermano(a)",
        asunto=message.subject,
        firma=_signature(actor),
        sitio=site_url,
    )


def mailto(message: ContactMessage, body: str = "") -> str:
    query = {"subject": f"Re: {message.subject}"}
    if body:
        query["body"] = body
    # Los clientes de correo esperan %20 y no "+" para los espacios.
    return f"mailto:{quote(message.email, safe='@')}?{urlencode(query, quote_via=quote)}"


def whatsapp_number(phone: str) -> str:
    digits = "".join(ch for ch in phone or "" if ch.isdigit())
    if len(digits) == 8:  # número de Guatemala sin código de país
        digits = "502" + digits
    return digits if 10 <= len(digits) <= 15 else ""


def options(message: ContactMessage, actor, site_url: str) -> list[dict]:
    number = whatsapp_number(message.phone)
    result = []
    for reply in REPLIES:
        if message.kind not in reply.kinds:
            continue
        body = render(reply, message, actor, site_url)
        text = urlencode({"text": body}, quote_via=quote)
        result.append(
            {
                "label": reply.label,
                "email_url": mailto(message, body),
                "whatsapp_url": f"https://wa.me/{number}?{text}" if number else "",
            }
        )
    return result
