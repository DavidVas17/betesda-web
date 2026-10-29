from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Cuenta del equipo. Los roles son grupos definidos en ``apps.accounts.roles``."""

    notify_new_messages = models.BooleanField(
        "avisarme de mensajes nuevos",
        default=True,
        help_text="Recibir un correo cuando llega una petición de oración o un mensaje.",
    )

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        permissions = [
            ("manage_team", "Puede gestionar las cuentas y roles del equipo"),
            ("view_activity", "Puede ver la bitácora de actividad"),
        ]

    @property
    def role_names(self) -> list[str]:
        from .roles import user_role_names

        return user_role_names(self)


class LoginAttempt(models.Model):
    """Intento fallido de ingreso. Sirve para frenar a quien prueba contraseñas."""

    username = models.CharField("usuario", max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField("dirección IP", null=True, blank=True)
    created_at = models.DateTimeField("fecha", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "intento fallido de ingreso"
        verbose_name_plural = "intentos fallidos de ingreso"

    def __str__(self) -> str:
        return f"{self.username} · {self.ip_address or 'IP desconocida'}"


class KnownDevice(models.Model):
    """Navegador desde el que una cuenta ya inició sesión. Se reconoce por una cookie."""

    user = models.ForeignKey(
        User, verbose_name="usuario", on_delete=models.CASCADE, related_name="known_devices"
    )
    key = models.CharField("huella", max_length=64, db_index=True)
    label = models.CharField("dispositivo", max_length=80)
    ip_address = models.GenericIPAddressField("última IP", null=True, blank=True)
    created_at = models.DateTimeField("primer ingreso", auto_now_add=True)
    last_seen = models.DateTimeField("último ingreso", auto_now_add=True)

    class Meta:
        ordering = ("-last_seen",)
        verbose_name = "dispositivo conocido"
        verbose_name_plural = "dispositivos conocidos"

    def __str__(self) -> str:
        return f"{self.user} · {self.label}"


class TwoFactorDevice(models.Model):
    """Verificación en dos pasos con una app de códigos (TOTP).

    El secreto se guarda en la base como lo hacen las bibliotecas habituales (django-otp):
    la base vive en una red interna sin acceso desde Internet y se respalda cifrada.
    """

    user = models.OneToOneField(
        User, verbose_name="usuario", on_delete=models.CASCADE, related_name="two_factor"
    )
    secret = models.CharField("secreto", max_length=64)
    confirmed_at = models.DateTimeField("activada", null=True, blank=True)
    last_step = models.BigIntegerField("último intervalo usado", default=0)
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        verbose_name = "verificación en dos pasos"
        verbose_name_plural = "verificaciones en dos pasos"

    def __str__(self) -> str:
        return f"{self.user} · {'activa' if self.confirmed_at else 'pendiente'}"

    @property
    def is_active(self) -> bool:
        return self.confirmed_at is not None


class RecoveryCode(models.Model):
    """Código de respaldo de un solo uso, por si se pierde el teléfono. Solo se guarda su huella."""

    user = models.ForeignKey(
        User, verbose_name="usuario", on_delete=models.CASCADE, related_name="recovery_codes"
    )
    code_hash = models.CharField("huella", max_length=64, db_index=True)
    used_at = models.DateTimeField("usado", null=True, blank=True)

    class Meta:
        verbose_name = "código de respaldo"
        verbose_name_plural = "códigos de respaldo"

    def __str__(self) -> str:
        return f"{self.user} · {'usado' if self.used_at else 'disponible'}"
