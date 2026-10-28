"""Freno a los intentos de adivinar contraseñas, en el panel y en la administración técnica.

Se cuentan los intentos fallidos en la base de datos (funciona igual con varios procesos):

- por usuario e IP: unos pocos fallos seguidos bloquean esa combinación un rato. Así nadie
  puede bloquear la cuenta de otra persona desde su propia conexión.
- por IP: un tope más alto frena a quien prueba muchos usuarios distintos.

Un ingreso correcto borra los fallos de esa combinación.
"""

import logging
import math
from datetime import timedelta

from django import forms
from django.conf import settings
from django.utils import timezone

from apps.core.network import client_ip

from .models import LoginAttempt

logger = logging.getLogger("apps.accounts.security")


def _normalize(username: str | None) -> str:
    return (username or "").strip().lower()[:150]


def _window_start(seconds: int):
    return timezone.now() - timedelta(seconds=seconds)


def seconds_until_allowed(username: str | None, ip: str | None) -> int:
    """0 si puede intentar; si no, los segundos que faltan para el próximo intento."""
    per_user, per_ip, window = settings.LOGIN_RATE_LIMIT
    since = _window_start(window)
    recent = LoginAttempt.objects.filter(created_at__gte=since)
    checks = [(recent.filter(username=_normalize(username), ip_address=ip), per_user)]
    if ip:
        checks.append((recent.filter(ip_address=ip), per_ip))
    wait = 0
    for queryset, limit in checks:
        times = list(queryset.order_by("-created_at").values_list("created_at", flat=True)[:limit])
        if len(times) >= limit:
            # Se libera cuando el fallo más antiguo de los últimos ``limit`` sale de la ventana.
            release = times[-1] + timedelta(seconds=window)
            wait = max(wait, math.ceil((release - timezone.now()).total_seconds()))
    return max(wait, 0)


def record_failure(username: str | None, ip: str | None, *, request=None) -> None:
    """Guarda el fallo y, si con él se alcanza un límite, avisa por correo (una sola vez)."""
    from .alerts import alert_login_locked

    name = _normalize(username)
    LoginAttempt.objects.create(username=name, ip_address=ip)
    per_user, per_ip, window = settings.LOGIN_RATE_LIMIT
    recent = LoginAttempt.objects.filter(created_at__gte=_window_start(window))
    if ip and recent.filter(ip_address=ip).count() == per_ip:
        alert_login_locked(name, ip, by_ip=True, request=request)
    elif recent.filter(username=name, ip_address=ip).count() == per_user:
        if name.startswith("2fa:"):
            alert_login_locked(name[4:], ip, by_ip=False, request=request, second_step=True)
        elif not name.startswith("reset:"):
            alert_login_locked(name, ip, by_ip=False, request=request)


def clear_failures(username: str | None, ip: str | None) -> None:
    LoginAttempt.objects.filter(username=_normalize(username), ip_address=ip).delete()


def purge_stale_devices(days: int = 365) -> int:
    """Olvida los navegadores que no se usan hace un año (guardan la última IP)."""
    from .models import KnownDevice

    deleted, _ = KnownDevice.objects.filter(
        last_seen__lt=timezone.now() - timedelta(days=days)
    ).delete()
    return deleted


def purge_old_attempts() -> int:
    """Borra intentos que ya no cuentan para ningún bloqueo (más de un día)."""
    deleted, _ = LoginAttempt.objects.filter(created_at__lt=_window_start(86400)).delete()
    return deleted


TOO_MANY_ATTEMPTS = (
    "Hubo demasiados intentos fallidos. Por seguridad, espera %(minutes)s antes de volver a "
    "intentarlo."
)


class ThrottledLoginMixin:
    """Para formularios basados en ``AuthenticationForm``."""

    def clean(self):
        username = self.cleaned_data.get("username")
        ip = client_ip(self.request) if self.request else None
        wait = seconds_until_allowed(username, ip)
        if wait:
            logger.warning("Ingreso bloqueado temporalmente: usuario=%s ip=%s", username, ip)
            minutes = max(1, math.ceil(wait / 60))
            raise forms.ValidationError(
                TOO_MANY_ATTEMPTS,
                code="too_many_attempts",
                params={"minutes": f"{minutes} minuto" + ("s" if minutes != 1 else "")},
            )
        try:
            cleaned = super().clean()
        except forms.ValidationError as error:
            if any(e.code == "invalid_login" for e in error.error_list):
                record_failure(username, ip, request=self.request)
            raise
        clear_failures(username, ip)
        return cleaned
