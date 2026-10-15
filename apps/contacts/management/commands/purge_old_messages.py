from django.core.management.base import BaseCommand

from apps.accounts.throttle import purge_old_attempts
from apps.contacts.retention import purge


class Command(BaseCommand):
    help = (
        "Elimina los mensajes cerrados o no deseados que cumplieron su plazo, borra las IP "
        "antiguas y limpia los intentos de ingreso viejos. Pensado para correr cada día."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra cuántos registros se eliminarían, sin borrar nada.",
        )

    def handle(self, *args, dry_run=False, **options):
        result = purge(dry_run=dry_run)
        attempts = 0 if dry_run else purge_old_attempts()
        verb = "Se eliminarían" if dry_run else "Eliminados"
        self.stdout.write(
            f"{verb}: {result.closed} cerrados y {result.spam} no deseados. "
            f"IP {'por borrar' if dry_run else 'borradas'}: {result.anonymized}. "
            f"Intentos de ingreso antiguos limpiados: {attempts}."
        )
