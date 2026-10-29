"""Defensas del formulario público contra bots y spam, de la más barata a la más costosa.

1. **Campo trampa** (``website``): invisible para personas; los bots lo llenan.
2. **Trampa de tiempo**: el formulario lleva la hora en que se mostró, firmada. Un envío en
   menos de unos segundos es un bot; uno sin firma válida, también.
3. **Cloudflare Turnstile** (opcional): verificación invisible "no soy un robot".
4. **Límite por IP y por correo**: frena a quien envía muchas veces seguidas.
5. **Duplicados**: el mismo mensaje del mismo correo en 24 horas no se guarda dos veces.
6. **Contenido**: muchos enlaces, palabras típicas de spam o texto en otro alfabeto marcan el
   mensaje como "No deseado": se guarda (por si fue un error) pero no se avisa al equipo.

A un bot detectado (1, 2) se le responde como si todo hubiera salido bien: así no aprende a
esquivar las trampas.
"""

import re
import time
import unicodedata
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone

from .models import ContactMessage

_SALT = "contacts.formulario"
FOREIGN_SCRIPTS = {"CYRILLIC", "CJK", "HIRAGANA", "KATAKANA", "HANGUL", "ARABIC", "THAI"}
URL_RE = re.compile(r"(https?://|www\.|\[url|<a\s)", re.IGNORECASE)
SPAM_WORDS = (
    "casino",
    "bitcoin",
    "crypto",
    "forex",
    "viagra",
    "cialis",
    "porn",
    "escort",
    "backlink",
    "seo service",
    "guest post",
    "loan offer",
    "investment opportunity",
    "telegram",
    "whatsapp me",
)


# --- Trampa de tiempo -----------------------------------------------------------------------------


def issue_timestamp() -> str:
    return signing.dumps(time.time(), salt=_SALT)


def time_trap_verdict(token: str) -> str | None:
    """``None`` si parece una persona; si no, el motivo (para el registro)."""
    limits = settings.CONTACT_TIME_TRAP
    if not limits:
        return None
    minimum, maximum = limits
    try:
        started = signing.loads(token or "", salt=_SALT, max_age=maximum)
    except signing.SignatureExpired:
        return None  # la persona tardó mucho: se acepta igual, no es señal de bot
    except signing.BadSignature:
        return "sin marca de tiempo válida"
    if time.time() - float(started) < minimum:
        return "enviado demasiado rápido"
    return None


# --- Contenido ----------------------------------------------------------------------------------


def _foreign_script_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    foreign = sum(
        1
        for ch in letters
        if unicodedata.name(ch, "").split(" ")[0]
        in {"CYRILLIC", "CJK", "HIRAGANA", "KATAKANA", "HANGUL", "ARABIC", "THAI"}
    )
    return foreign / len(letters)


def spam_reasons(*, name: str, subject: str, message: str) -> list[str]:
    reasons = []
    if len(URL_RE.findall(message)) >= 3:
        reasons.append("muchos enlaces")
    if URL_RE.search(name) or URL_RE.search(subject):
        reasons.append("enlace en el nombre o el asunto")
    text = f"{subject} {message}".lower()
    words = [word for word in SPAM_WORDS if re.search(rf"\b{re.escape(word)}\b", text)]
    if words:
        reasons.append("palabras de spam: " + ", ".join(words))
    if _foreign_script_ratio(f"{name} {subject} {message}") > 0.3:
        reasons.append("texto en otro alfabeto")
    return reasons


# --- Repeticiones -------------------------------------------------------------------------------


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def is_duplicate(email: str, message: str) -> bool:
    since = timezone.now() - timedelta(hours=24)
    recent = ContactMessage.objects.filter(email__iexact=email, created_at__gte=since)
    target = _normalize(message)
    return any(_normalize(text) == target for text in recent.values_list("message", flat=True))


def too_many_from_email(email: str) -> bool:
    limit, seconds = settings.CONTACT_EMAIL_RATE_LIMIT
    since = timezone.now() - timedelta(seconds=seconds)
    return (
        ContactMessage.objects.filter(email__iexact=email, created_at__gte=since).count() >= limit
    )
