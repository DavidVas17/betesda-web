"""Protección del formulario público: IP real del visitante y límite de envíos."""

import ipaddress
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import ContactMessage


def client_ip(request) -> str | None:
    """IP del visitante.

    En producción el sitio está detrás de Caddy: ``REMOTE_ADDR`` es la IP de Caddy y la del
    visitante llega en ``X-Forwarded-For``. Solo se confía en ese encabezado cuando
    ``TRUST_X_FORWARDED_FOR`` está activo; se toma la última IP, que es la que agregó nuestro
    propio proxy y un visitante no puede falsificar.
    """
    candidate = request.META.get("REMOTE_ADDR", "")
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            candidate = hops[-1]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def too_many_recent_messages(ip: str | None) -> bool:
    """Más de ``CONTACT_RATE_LIMIT`` mensajes desde la misma IP en la ventana configurada.

    Se cuenta en la base de datos, así funciona igual con varios procesos del servidor y no
    necesita infraestructura adicional.
    """
    if not ip:
        return False
    limit, window_seconds = settings.CONTACT_RATE_LIMIT
    since = timezone.now() - timedelta(seconds=window_seconds)
    return ContactMessage.objects.filter(source_ip=ip, created_at__gte=since).count() >= limit
