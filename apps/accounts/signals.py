from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User
from .roles import sync_user_role


@receiver(post_save, sender=User)
def apply_role_group(sender, instance, **kwargs) -> None:
    """Mantiene el grupo de permisos alineado con el rol cada vez que se guarda un usuario."""
    if kwargs.get("raw"):
        return
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and "role" not in update_fields:
        return  # p. ej. el registro de ultimo inicio de sesion
    sync_user_role(instance)
