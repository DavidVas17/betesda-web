"""Protección del formulario público: límite de envíos por IP."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.core.network import client_ip

from .models import ContactMessage

__all__ = ["client_ip", "too_many_recent_messages"]


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
