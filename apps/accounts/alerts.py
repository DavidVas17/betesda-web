"""Avisos de seguridad por correo.

Llegan a quien debe enterarse sin tener que revisar la bitácora:

- **Ingreso bloqueado** por intentos fallidos: a la persona dueña de la cuenta y a quienes
  administran (superusuario, Administración de la iglesia y ``SECURITY_ALERT_EMAILS``).
- **Inicio de sesión desde un dispositivo nuevo**: a la persona, para que note si no fue ella.
- **Cuenta nueva** y **privilegios de administración otorgados**: a quienes administran.

Ningún aviso incluye contraseñas ni el contenido de mensajes. Un fallo de correo nunca
interrumpe la acción que lo provocó.
"""

import hashlib
import logging
import re
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from apps.core.network import client_ip

logger = logging.getLogger("apps.accounts.security")

DEVICE_COOKIE = "betesda_dispositivo"
DEVICE_COOKIE_AGE = 2 * 365 * 24 * 3600


# --- Destinatarios y envío -------------------------------------------------------------------


def admin_recipients(exclude=None) -> list[str]:
    """Superusuarios, quienes gestionan el equipo y los correos extra de la configuración."""
    manage_team = Permission.objects.filter(
        content_type__app_label="accounts", codename="manage_team"
    )
    users = (
        get_user_model()
        .objects.filter(is_active=True)
        .exclude(email="")
        .filter(
            Q(is_superuser=True)
            | Q(groups__permissions__in=manage_team)
            | Q(user_permissions__in=manage_team)
        )
        .distinct()
    )
    if exclude is not None:
        users = users.exclude(pk=exclude.pk)
    emails = {user.email for user in users} | set(settings.SECURITY_ALERT_EMAILS)
    return sorted(email for email in emails if email)


def send_alert(subject: str, body: str, *, to=(), bcc=()) -> None:
    """Envía el aviso cuando termina la transacción en curso (o de inmediato si no hay)."""
    to, bcc = [e for e in to if e], [e for e in bcc if e and e not in to]
    if not (to or bcc):
        return

    def deliver():
        message = EmailMessage(
            subject=f"[Betesda · Seguridad] {subject}",
            body=body + "\n—\nAviso automático del panel de Betesda Rosa de Sarón.\n",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to,
            bcc=bcc,
        )
        try:
            message.send()
        except Exception:  # noqa: BLE001 - el aviso nunca debe romper la acción
            logger.exception("No se pudo enviar el aviso de seguridad: %s", subject)

    transaction.on_commit(deliver)


def absolute_url(path: str, request=None) -> str:
    if request is not None:
        return request.build_absolute_uri(path)
    return settings.SITE_URL.rstrip("/") + path if settings.SITE_URL else path


def _now() -> str:
    return date_format(timezone.localtime(), "j \\d\\e F \\d\\e Y, H:i")


# --- Dispositivo ----------------------------------------------------------------------------


def device_label(user_agent: str) -> str:
    """Descripción legible del navegador, por ejemplo «Chrome en Windows»."""
    ua = user_agent or ""
    browsers = (
        (r"Edg/", "Edge"),
        (r"OPR/|Opera", "Opera"),
        (r"SamsungBrowser", "Samsung Internet"),
        (r"Firefox/|FxiOS", "Firefox"),
        (r"Chrome/|CriOS", "Chrome"),
        (r"Safari/", "Safari"),
    )
    systems = (
        (r"iPhone|iPad", "iPhone/iPad"),
        (r"Android", "Android"),
        (r"Windows", "Windows"),
        (r"Mac OS X|Macintosh", "Mac"),
        (r"Linux", "Linux"),
    )
    browser = next((name for pattern, name in browsers if re.search(pattern, ua)), "Navegador")
    system = next((name for pattern, name in systems if re.search(pattern, ua)), "")
    return f"{browser} en {system}" if system else browser


def hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def remember_device(request, user) -> None:
    """Al iniciar sesión: si el dispositivo es nuevo para esta cuenta, lo guarda y avisa.

    El dispositivo se reconoce por una cookie aleatoria; en la base solo se guarda su huella.
    El primer ingreso de una cuenta no genera aviso.
    """
    from .models import KnownDevice

    ip = client_ip(request)
    label = device_label(request.META.get("HTTP_USER_AGENT", ""))
    token = request.COOKIES.get(DEVICE_COOKIE, "")
    if token:
        device = KnownDevice.objects.filter(user=user, key=hash_device_token(token)).first()
        if device:
            device.last_seen = timezone.now()
            device.ip_address = ip
            device.label = label
            device.save(update_fields=("last_seen", "ip_address", "label"))
            return
    first_login = not KnownDevice.objects.filter(user=user).exists()
    token = token or secrets.token_urlsafe(32)
    KnownDevice.objects.create(user=user, key=hash_device_token(token), label=label, ip_address=ip)
    request.device_cookie = token
    if not first_login and user.email:
        password_url = absolute_url(reverse("panel:password_reset"), request)
        send_alert(
            "Nuevo inicio de sesión en tu cuenta",
            f"Hola {user.get_short_name() or user.get_username()}:\n\n"
            f"Se inició sesión en tu cuenta del panel desde un dispositivo que no "
            f"habíamos visto.\n\n"
            f"Dispositivo: {label}\nIP: {ip or 'desconocida'}\nFecha: {_now()}\n\n"
            f"Si fuiste tú, no tienes que hacer nada.\n"
            f"Si no fuiste tú, cambia tu contraseña de inmediato:\n{password_url}\n"
            f"y avisa al administrador de la iglesia.\n",
            to=[user.email],
        )


class DeviceCookieMiddleware:
    """Entrega la cookie del dispositivo recién reconocido al iniciar sesión."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        token = getattr(request, "device_cookie", None)
        if token:
            response.set_cookie(
                DEVICE_COOKIE,
                token,
                max_age=DEVICE_COOKIE_AGE,
                secure=settings.SESSION_COOKIE_SECURE,
                httponly=True,
                samesite="Lax",
            )
        return response


# --- Bloqueos, cuentas y privilegios ---------------------------------------------------------


def alert_login_locked(username: str, ip: str | None, *, by_ip: bool, request=None) -> None:
    window = max(1, settings.LOGIN_RATE_LIMIT[2] // 60)
    where = f"IP: {ip or 'desconocida'}\nFecha: {_now()}\n"
    if by_ip:
        send_alert(
            "Ingreso bloqueado por muchos intentos desde una conexión",
            "Se bloqueó temporalmente una conexión que probó contraseñas con varios "
            f"usuarios distintos.\n\n{where}Último usuario probado: {username or '—'}\n\n"
            f"El bloqueo dura {window} minutos. Si se repite, conviene revisar la "
            "bitácora y bloquear esa IP en el servidor.\n",
            bcc=admin_recipients(),
        )
        return
    user = (
        get_user_model()
        .objects.filter(username__iexact=username, is_active=True)
        .exclude(email="")
        .first()
    )
    if user is None:
        # Usuario inexistente: no se avisa a nadie por correo (sería ruido); queda en el log.
        logger.warning("Bloqueo de ingreso para usuario inexistente %s desde %s", username, ip)
        return
    reset_url = absolute_url(reverse("panel:password_reset"), request)
    send_alert(
        "Varios intentos fallidos de ingreso en tu cuenta",
        f"Hola {user.get_short_name() or user.get_username()}:\n\n"
        f"Alguien escribió mal la contraseña de tu cuenta varias veces seguidas, así que "
        f"bloqueamos el ingreso desde esa conexión por {window} minutos.\n\n{where}\n"
        f"Si fuiste tú, espera y vuelve a intentar, o recupera tu contraseña:\n{reset_url}\n"
        f"Si no fuiste tú, tu contraseña sigue a salvo; considera cambiarla por una más "
        f"larga.\n",
        to=[user.email],
        bcc=admin_recipients(exclude=user),
    )


def alert_account_created(actor, user, roles) -> None:
    send_alert(
        "Se creó una cuenta en el panel",
        f"{actor.get_full_name() or actor.get_username()} creó la cuenta "
        f"«{user.get_username()}».\n\nRoles: {', '.join(roles) or 'sin roles'}\n"
        f"Fecha: {_now()}\n\n"
        f"Si no esperabas este cambio, revisa la sección Usuarios del panel:\n"
        f"{absolute_url(reverse('panel:user_list'))}\n",
        bcc=admin_recipients(exclude=actor),
    )


def alert_privilege_granted(user, privilege: str) -> None:
    send_alert(
        "Se otorgaron privilegios de administración",
        f"La cuenta «{user.get_username()}» recibió: {privilege}.\nFecha: {_now()}\n\n"
        f"Con esto puede gestionar al equipo. Si no reconoces el cambio, revísalo de "
        f"inmediato en el panel o en la administración técnica.\n",
        to=[user.email] if user.email else [],
        bcc=admin_recipients(exclude=user),
    )


def alert_password_changed(user, *, by=None, request=None) -> None:
    """A la persona, cada vez que su contraseña cambia (por ella, por correo o por otra)."""
    if not user.email:
        return
    who = (
        f"{by.get_full_name() or by.get_username()} (administración del equipo)"
        if by is not None and by.pk != user.pk
        else "tú mismo, desde tu cuenta o con el enlace de recuperación"
    )
    send_alert(
        "Tu contraseña cambió",
        f"Hola {user.get_short_name() or user.get_username()}:\n\n"
        f"La contraseña de tu cuenta del panel cambió.\n\nQuién: {who}\nFecha: {_now()}\n"
        f"IP: {(client_ip(request) if request else None) or 'desconocida'}\n\n"
        f"Si no reconoces este cambio, avisa de inmediato al administrador de la iglesia.\n",
        to=[user.email],
    )
