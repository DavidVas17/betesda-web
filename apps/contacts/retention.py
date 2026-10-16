"""Cuánto tiempo se guardan los mensajes y peticiones de oración.

Son datos personales y a veces muy sensibles (salud, familia, problemas personales), así que
no se guardan para siempre:

- Los **cerrados** se eliminan ``MESSAGE_RETENTION_DAYS`` después de su último cambio.
- Los marcados como **no deseados** se eliminan ``SPAM_RETENTION_DAYS`` después.
- La **IP** de cada envío solo sirve para frenar abusos; se borra a los ``IP_RETENTION_DAYS``.

Los mensajes nuevos o en seguimiento nunca se eliminan solos: alguien del equipo debe
cerrarlos primero.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ContactMessage


@dataclass(frozen=True)
class PurgeResult:
    closed: int
    spam: int
    anonymized: int

    @property
    def deleted(self) -> int:
        return self.closed + self.spam


def _before(days: int):
    return timezone.now() - timedelta(days=days)


def expired_messages():
    """Mensajes que ya cumplieron su plazo, separados por motivo."""
    closed = ContactMessage.objects.filter(
        status=ContactMessage.Status.CLOSED,
        updated_at__lt=_before(settings.MESSAGE_RETENTION_DAYS),
    )
    spam = ContactMessage.objects.filter(
        status=ContactMessage.Status.SPAM,
        updated_at__lt=_before(settings.SPAM_RETENTION_DAYS),
    )
    return closed, spam


def ips_to_forget():
    return ContactMessage.objects.filter(
        source_ip__isnull=False, created_at__lt=_before(settings.IP_RETENTION_DAYS)
    )


def purge(*, dry_run: bool = False) -> PurgeResult:
    closed, spam = expired_messages()
    ips = ips_to_forget()
    if dry_run:
        return PurgeResult(closed.count(), spam.count(), ips.count())
    with transaction.atomic():
        closed_count, _ = closed.delete()
        spam_count, _ = spam.delete()
        # ``update`` no toca ``updated_at``: borrar la IP no reinicia el plazo del mensaje.
        anonymized = ips.update(source_ip=None)
    return PurgeResult(closed_count, spam_count, anonymized)
