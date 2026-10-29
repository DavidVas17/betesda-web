import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

EXAMPLE_PASSWORD = "replace-me-before-use"


class Command(BaseCommand):
    help = (
        "Crea el superusuario inicial con las variables DJANGO_SUPERUSER_*. Si ya existe, "
        "actualiza su correo y lo deja activo, pero NO cambia su contraseña salvo que uses "
        "--reset-password."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Reemplaza la contraseña existente por la de DJANGO_SUPERUSER_PASSWORD.",
        )

    def handle(self, *args, reset_password=False, **options) -> None:
        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not all((username, email, password)):
            message = "Configure las tres variables DJANGO_SUPERUSER_* antes de continuar."
            raise CommandError(message)

        user_model = get_user_model()
        user = user_model.objects.filter(username=username).first()
        created = user is None
        sets_password = created or reset_password
        if sets_password:
            if password == EXAMPLE_PASSWORD:
                raise CommandError(
                    "Cambie DJANGO_SUPERUSER_PASSWORD antes de ejecutar este comando."
                )
            candidate = user or user_model(username=username, email=email)
            try:
                validate_password(password, candidate)
            except ValidationError as error:
                problems = " ".join(error.messages)
                raise CommandError(f"DJANGO_SUPERUSER_PASSWORD no es segura: {problems}") from error

        user = user or user_model(username=username)
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if sets_password:
            user.set_password(password)
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Administrador creado: {username}"))
        elif reset_password:
            self.stdout.write(
                self.style.SUCCESS(f"Administrador actualizado y contraseña cambiada: {username}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Administrador actualizado: {username} (correo y permisos). La contraseña no "
                    "cambió; usa --reset-password si quieres reemplazarla."
                )
            )
