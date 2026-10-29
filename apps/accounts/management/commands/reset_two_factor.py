from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import two_factor


class Command(BaseCommand):
    help = (
        "Quita la verificación en dos pasos de una cuenta (por ejemplo, el superusuario perdió "
        "su teléfono y sus códigos). Al ingresar, la configurará de nuevo."
    )

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **options):
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"No existe la cuenta «{username}».")
        two_factor.disable(user)
        self.stdout.write(self.style.SUCCESS(f"Verificación restablecida para {username}."))
