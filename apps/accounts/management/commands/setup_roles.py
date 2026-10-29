from django.core.management.base import BaseCommand

from apps.accounts.roles import ROLES, ensure_role_groups


class Command(BaseCommand):
    help = "Crea o actualiza los grupos de cada rol con los permisos definidos en código."

    def handle(self, *args, **options) -> None:
        ensure_role_groups()
        self.stdout.write(self.style.SUCCESS(f"Roles aplicados: {len(ROLES)}"))
