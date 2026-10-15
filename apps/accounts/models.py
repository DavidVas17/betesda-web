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
