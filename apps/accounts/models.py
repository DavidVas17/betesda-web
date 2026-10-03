from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        EDITOR = "EDITOR", "Editor de contenido"

    role = models.CharField("rol", max_length=20, choices=Role.choices, default=Role.EDITOR)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

