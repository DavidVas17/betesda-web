from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .roles import ensure_role_groups


@receiver(post_migrate)
def sync_role_groups(sender, using="default", **kwargs) -> None:
    """Después de cada ``migrate`` los grupos quedan con los permisos definidos en código.

    ``post_migrate`` se emite una vez por app instalada y Django crea los permisos de cada
    app justo antes; tras la última, todos los permisos existen y los grupos quedan completos.
    Son seis grupos, así que repetirlo por app no tiene costo apreciable.
    """
    if using != "default":
        return
    ensure_role_groups()
