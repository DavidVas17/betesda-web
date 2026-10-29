"""Agregar un evento al calendario del teléfono (archivo .ics) o a Google Calendar, y
compartirlo por WhatsApp o Facebook."""

from datetime import UTC, timedelta
from urllib.parse import quote, urlencode

from django.utils import timezone
from django.utils.formats import date_format

DEFAULT_DURATION = timedelta(hours=2)
_STAMP = "%Y%m%dT%H%M%SZ"


def _end(event):
    return event.ends_at or event.starts_at + DEFAULT_DURATION


def _utc(moment) -> str:
    return moment.astimezone(UTC).strftime(_STAMP)


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """RFC 5545: líneas de máximo 75 octetos; las siguientes empiezan con un espacio."""
    encoded = line.encode()
    if len(encoded) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        piece = char.encode()
        if len(current) + len(piece) > (75 if not parts else 74):
            parts.append(current.decode())
            current = b""
        current += piece
    parts.append(current.decode())
    return "\r\n ".join(parts)


def ics(event, url: str) -> str:
    description = f"{event.summary}\n\n{url}"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Betesda Rosa de Saron//Sitio web//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:evento-{event.pk}@betesda-rosa-de-saron",
        f"DTSTAMP:{_utc(timezone.now())}",
        f"DTSTART:{_utc(event.starts_at)}",
        f"DTEND:{_utc(_end(event))}",
        f"SUMMARY:{_escape(event.title)}",
        f"LOCATION:{_escape(event.location)}",
        f"DESCRIPTION:{_escape(description)}",
        f"URL:{url}",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_escape(event.title)}",
        "TRIGGER:-PT2H",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def google_calendar_url(event, url: str) -> str:
    query = {
        "action": "TEMPLATE",
        "text": event.title,
        "dates": f"{_utc(event.starts_at)}/{_utc(_end(event))}",
        "details": f"{event.summary}\n\n{url}",
        "location": event.location,
        "ctz": "America/Guatemala",
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(query, quote_via=quote)


def share_text(event, url: str) -> str:
    when = date_format(timezone.localtime(event.starts_at), "l j \\d\\e F, H:i")
    return f"{event.title} · {when} h · {event.location}\n{url}"


def whatsapp_url(event, url: str) -> str:
    return "https://wa.me/?" + urlencode({"text": share_text(event, url)}, quote_via=quote)


def facebook_url(url: str) -> str:
    return "https://www.facebook.com/sharer/sharer.php?" + urlencode({"u": url}, quote_via=quote)
