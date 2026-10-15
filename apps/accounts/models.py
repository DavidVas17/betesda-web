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
