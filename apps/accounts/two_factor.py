"""Verificación en dos pasos: activar, comprobar códigos y códigos de respaldo.

Las vistas del panel solo llaman a estas funciones; aquí vive la lógica de seguridad.
"""

import hashlib
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import totp
from .models import RecoveryCode, TwoFactorDevice

ISSUER = "Betesda Rosa de Sarón"
RECOVERY_CODE_COUNT = 10
# Sin 0/O, 1/l/I ni 5/S: los códigos se copian a mano desde un papel.
_ALPHABET = "abcdefghjkmnpqrtuvwxyz2346789"


def device_for(user) -> TwoFactorDevice | None:
    # Consulta directa (sin la caché de ``user.two_factor``): el estado puede cambiar en la
    # misma petición, por ejemplo al activarla o restablecerla.
    return TwoFactorDevice.objects.filter(user_id=user.pk).first()


def is_enabled(user) -> bool:
    if not getattr(user, "pk", None):
        return False
    return TwoFactorDevice.objects.filter(user_id=user.pk, confirmed_at__isnull=False).exists()


def is_required(user) -> bool:
    """Quien administra (superusuario o gestiona al equipo) debe tenerla activa."""
    if not settings.TWO_FACTOR_ENFORCE or not user.is_authenticated:
        return False
    return user.is_superuser or user.has_perm("accounts.manage_team")


def start_setup(user) -> TwoFactorDevice:
    """Secreto nuevo pendiente de confirmar. Si ya había uno pendiente, se reutiliza."""
    device = device_for(user)
    if device is None:
        return TwoFactorDevice.objects.create(user=user, secret=totp.generate_secret())
    if device.is_active:
        raise ValueError("La verificación ya está activa.")
    return device


def provisioning_uri(device: TwoFactorDevice) -> str:
    return totp.provisioning_uri(device.secret, device.user.get_username(), ISSUER)


def _use_code(device: TwoFactorDevice, code: str) -> bool:
    step = totp.matching_step(device.secret, code, last_step=device.last_step)
    if step is None:
        return False
    device.last_step = step
    device.save(update_fields=("last_step",))
    return True


@transaction.atomic
def confirm_setup(user, code: str) -> list[str] | None:
    """Activa la verificación si el código es correcto y devuelve los códigos de respaldo."""
    device = TwoFactorDevice.objects.select_for_update().filter(user=user).first()
    if device is None or device.is_active or not _use_code(device, code):
        return None
    device.confirmed_at = timezone.now()
    device.save(update_fields=("confirmed_at",))
    return regenerate_recovery_codes(user)


def _hash(code: str) -> str:
    return hashlib.sha256(normalize_recovery_code(code).encode()).hexdigest()


def normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in str(code).lower() if ch.isalnum())


def regenerate_recovery_codes(user) -> list[str]:
    """Reemplaza los códigos de respaldo. Los anteriores dejan de servir."""
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    RecoveryCode.objects.filter(user=user).delete()
    RecoveryCode.objects.bulk_create(RecoveryCode(user=user, code_hash=_hash(c)) for c in codes)
    return codes


def remaining_recovery_codes(user) -> int:
    return RecoveryCode.objects.filter(user=user, used_at__isnull=True).count()


@transaction.atomic
def verify(user, code: str) -> str | None:
    """Comprueba un código al ingresar. Devuelve "app", "respaldo" o ``None``."""
    device = TwoFactorDevice.objects.select_for_update().filter(user=user).first()
    if device is None or not device.is_active:
        return None
    if _use_code(device, code):
        return "app"
    normalized = normalize_recovery_code(code)
    if len(normalized) == 10:
        used = RecoveryCode.objects.filter(
            user=user, code_hash=_hash(normalized), used_at__isnull=True
        ).update(used_at=timezone.now())
        if used:
            return "respaldo"
    return None


@transaction.atomic
def disable(user) -> None:
    TwoFactorDevice.objects.filter(user=user).delete()
    RecoveryCode.objects.filter(user=user).delete()
