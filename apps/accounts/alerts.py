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
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.emails import Email, now_label
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


def send_alert(email: Email, *, to=(), bcc=()) -> None:
    """Envía el aviso cuando termina la transacción en curso (o de inmediato si no hay)."""
    to, bcc = [e for e in to if e], [e for e in bcc if e and e not in to]
    if not (to or bcc):
        return
    email.subject = f"[Betesda · Seguridad] {email.subject}"
    email.eyebrow = "Seguridad del panel"
    email.tone = "alert"
    email.footer = email.footer or (
        "Aviso automático del panel de Betesda Rosa de Sarón. Por seguridad, nunca te "
        "pediremos tu contraseña por correo."
    )

    def deliver():
        try:
            email.message(to=to, bcc=bcc).send()
        except Exception:  # noqa: BLE001 - el aviso nunca debe romper la acción
            logger.exception("No se pudo enviar el aviso de seguridad: %s", email.subject)

    transaction.on_commit(deliver)


def absolute_url(path: str, request=None) -> str:
    if request is not None:
        return request.build_absolute_uri(path)
    return settings.SITE_URL.rstrip("/") + path if settings.SITE_URL else path


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


def current_device_key(request) -> str:
    """Huella del navegador actual, para marcarlo en la lista de dispositivos."""
    token = request.COOKIES.get(DEVICE_COOKIE, "") or getattr(request, "device_cookie", "")
    return hash_device_token(token) if token else ""


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
        send_alert(
            Email(
                subject="Nuevo inicio de sesión en tu cuenta",
                title="Nuevo inicio de sesión",
                preheader=f"Se inició sesión en tu cuenta desde {label}.",
                paragraphs=[
                    f"Hola {_name(user)}:",
                    "Se inició sesión en tu cuenta del panel desde un dispositivo que no "
                    "habíamos visto. Si fuiste tú, no tienes que hacer nada.",
                ],
                details=[
                    ("Dispositivo", label),
                    ("IP", ip or "desconocida"),
                    ("Fecha", now_label()),
                ],
                button=(
                    "No fui yo: cambiar contraseña",
                    absolute_url(reverse("panel:password_reset"), request),
                ),
                note="Si no reconoces este ingreso, cambia tu contraseña de inmediato y avisa "
                "al administrador de la iglesia.",
            ),
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


def _name(user) -> str:
    return user.get_short_name() or user.get_full_name() or user.get_username()


def alert_login_locked(
    username: str, ip: str | None, *, by_ip: bool, request=None, second_step: bool = False
) -> None:
    window = max(1, settings.LOGIN_RATE_LIMIT[2] // 60)
    if by_ip:
        send_alert(
            Email(
                subject="Ingreso bloqueado por muchos intentos desde una conexión",
                title="Conexión bloqueada temporalmente",
                paragraphs=[
                    "Una conexión probó contraseñas con varios usuarios distintos y la "
                    f"bloqueamos durante {window} minutos.",
                ],
                details=[
                    ("IP", ip or "desconocida"),
                    ("Último usuario probado", username or "—"),
                    ("Fecha", now_label()),
                ],
                note="Si se repite, conviene revisar la bitácora y bloquear esa IP en el servidor.",
            ),
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
    if second_step:
        send_alert(
            Email(
                subject="Tu contraseña fue usada y se bloqueó el segundo paso",
                title="Alguien tiene tu contraseña",
                paragraphs=[
                    f"Hola {_name(user)}:",
                    "Alguien escribió tu contraseña correcta, pero falló varias veces el código "
                    "de verificación. La verificación en dos pasos lo detuvo y bloqueamos esa "
                    f"conexión durante {window} minutos.",
                ],
                details=[
                    ("Cuenta", user.get_username()),
                    ("IP", ip or "desconocida"),
                    ("Fecha", now_label()),
                ],
                button=(
                    "Cambiar mi contraseña ahora",
                    absolute_url(reverse("panel:password_reset"), request),
                ),
                note="Si no fuiste tú, cambia tu contraseña de inmediato: la otra persona ya "
                "la conoce.",
            ),
            to=[user.email],
            bcc=admin_recipients(exclude=user),
        )
        return
    send_alert(
        Email(
            subject="Varios intentos fallidos de ingreso en tu cuenta",
            title="Intentos fallidos en tu cuenta",
            paragraphs=[
                f"Hola {_name(user)}:",
                "Alguien escribió mal la contraseña de tu cuenta varias veces seguidas, así "
                f"que bloqueamos el ingreso desde esa conexión durante {window} minutos.",
            ],
            details=[
                ("Cuenta", user.get_username()),
                ("IP", ip or "desconocida"),
                ("Fecha", now_label()),
            ],
            button=(
                "Recuperar mi contraseña",
                absolute_url(reverse("panel:password_reset"), request),
            ),
            note="Si no fuiste tú, tu contraseña sigue a salvo: nadie entró. Aun así, "
            "considera cambiarla por una más larga.",
        ),
        to=[user.email],
        bcc=admin_recipients(exclude=user),
    )


def alert_account_created(actor, user, roles) -> None:
    send_alert(
        Email(
            subject="Se creó una cuenta en el panel",
            title="Nueva cuenta en el panel",
            paragraphs=[
                f"{actor.get_full_name() or actor.get_username()} creó una cuenta nueva "
                "para el equipo.",
            ],
            details=[
                ("Cuenta", user.get_username()),
                ("Roles", ", ".join(roles) or "sin roles"),
                ("Creada por", actor.get_username()),
                ("Fecha", now_label()),
            ],
            button=("Revisar usuarios", absolute_url(reverse("panel:user_list"))),
            note="Si no esperabas este cambio, revísalo en la sección Usuarios del panel.",
        ),
        bcc=admin_recipients(exclude=actor),
    )


def alert_privilege_granted(user, privilege: str) -> None:
    send_alert(
        Email(
            subject="Se otorgaron privilegios de administración",
            title="Nuevos privilegios de administración",
            paragraphs=[
                f"La cuenta «{user.get_username()}» recibió {privilege}. Con esto puede "
                "gestionar al equipo.",
            ],
            details=[("Cuenta", user.get_username()), ("Fecha", now_label())],
            note="Si no reconoces este cambio, revísalo de inmediato en el panel o en la "
            "administración técnica.",
        ),
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
        else "Tú, desde tu cuenta o con el enlace de recuperación"
    )
    send_alert(
        Email(
            subject="Tu contraseña cambió",
            title="Tu contraseña cambió",
            paragraphs=[f"Hola {_name(user)}:", "La contraseña de tu cuenta del panel cambió."],
            details=[
                ("Quién", who),
                ("IP", (client_ip(request) if request else None) or "desconocida"),
                ("Fecha", now_label()),
            ],
            note="Si no reconoces este cambio, avisa de inmediato al administrador de la iglesia.",
        ),
        to=[user.email],
    )


def alert_two_factor_changed(user, *, enabled: bool, by=None, request=None) -> None:
    """A la persona (y a quienes administran si la quitó otra persona)."""
    by_other = by is not None and by.pk != user.pk
    if enabled:
        title, text = (
            "Verificación en dos pasos activada",
            "Desde ahora, además de tu contraseña, el panel te pedirá un código de tu app.",
        )
    elif by_other:
        title, text = (
            "Tu verificación en dos pasos fue restablecida",
            f"{by.get_full_name() or by.get_username()} restableció tu verificación en dos "
            "pasos, por ejemplo porque cambiaste de teléfono. Configúrala de nuevo al ingresar.",
        )
    else:
        title, text = (
            "Verificación en dos pasos desactivada",
            "Quitaste la verificación en dos pasos de tu cuenta.",
        )
    send_alert(
        Email(
            subject=title,
            title=title,
            paragraphs=[f"Hola {_name(user)}:", text],
            details=[
                ("Cuenta", user.get_username()),
                ("IP", (client_ip(request) if request else None) or "desconocida"),
                ("Fecha", now_label()),
            ],
            note="Si no reconoces este cambio, avisa de inmediato al administrador de la iglesia.",
        ),
        to=[user.email] if user.email else [],
        bcc=admin_recipients(exclude=user) if (by_other or not enabled) else [],
    )


def alert_recovery_code_used(user, *, request=None) -> None:
    from .two_factor import remaining_recovery_codes

    remaining = remaining_recovery_codes(user)
    send_alert(
        Email(
            subject="Se usó un código de respaldo",
            title="Se usó un código de respaldo",
            paragraphs=[
                f"Hola {_name(user)}:",
                "Alguien ingresó a tu cuenta con uno de tus códigos de respaldo en lugar del "
                "código de tu app.",
            ],
            details=[
                ("Códigos que te quedan", str(remaining)),
                ("IP", (client_ip(request) if request else None) or "desconocida"),
                ("Fecha", now_label()),
            ],
            note="Si no fuiste tú, cambia tu contraseña y genera códigos nuevos en Mi cuenta "
            "de inmediato.",
        ),
        to=[user.email] if user.email else [],
        bcc=admin_recipients(exclude=user),
    )
