from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.roles import ensure_role_groups, sync_user_role


class Command(BaseCommand):
    help = "Crea/actualiza los grupos de permisos por rol y los asigna a los usuarios existentes."

    def handle(self, *args, **options) -> None:
        ensure_role_groups()
        users = list(User.objects.all())
        for user in users:
            sync_user_role(user)
        self.stdout.write(
            self.style.SUCCESS(f"Roles aplicados. Usuarios sincronizados: {len(users)}")
        )
