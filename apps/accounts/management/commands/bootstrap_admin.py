import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea o actualiza el administrador inicial usando variables de entorno."

    def handle(self, *args, **options) -> None:
        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not all((username, email, password)):
            message = "Configure las tres variables DJANGO_SUPERUSER_* antes de continuar."
            raise CommandError(message)
        if password == "replace-me-before-use":
            raise CommandError("Cambie DJANGO_SUPERUSER_PASSWORD antes de ejecutar este comando.")

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.role = user_model.Role.ADMIN
        user.set_password(password)
        user.save()

        action = "creado" if created else "actualizado"
        self.stdout.write(self.style.SUCCESS(f"Administrador {action}: {username}"))
