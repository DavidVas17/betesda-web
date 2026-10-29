"""Cloudflare Turnstile: verificación "no soy un robot" sin acertijos ni imágenes.

Opcional y gratuito. Se activa con ``TURNSTILE_SITE_KEY`` y ``TURNSTILE_SECRET_KEY`` (se
obtienen en el panel de Cloudflare → Turnstile). Sin las claves, el formulario funciona igual
con las demás defensas.
"""

import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js"
FIELD = "cf-turnstile-response"


def enabled() -> bool:
    return bool(settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY)


def verify(token: str, ip: str | None) -> bool:
    """``True`` si Cloudflare confirma que es una persona.

    Si Cloudflare no responde, se acepta el envío (y se registra): una petición de oración
    no debe perderse porque un servicio externo esté caído; las demás defensas siguen activas.
    """
    if not enabled():
        return True
    if not token:
        return False
    data = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if ip:
        data["remoteip"] = ip
    request = urllib.request.Request(
        VERIFY_URL, data=urllib.parse.urlencode(data).encode(), method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - URL fija
            return bool(json.load(response).get("success"))
    except (OSError, ValueError):
        logger.warning("Turnstile no respondió; se acepta el envío con las demás defensas.")
        return True
