from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import m2m_changed, post_migrate, post_save, pre_save
from django.dispatch import receiver

from .alerts import alert_privilege_granted, remember_device
from .roles import PRIVILEGED_ROLE_NAMES, ensure_role_groups

User = get_user_model()


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


@receiver(user_logged_in)
def track_device(sender, request, user, **kwargs) -> None:
    if request is not None:
        remember_device(request, user)


@receiver(m2m_changed, sender=User.groups.through)
def privileged_role_added(sender, instance, action, reverse, pk_set, **kwargs) -> None:
    """Avisa cuando alguien recibe un rol que permite gestionar al equipo, venga de donde venga."""
    if action != "post_add" or not pk_set:
        return
    if reverse:  # group.user_set.add(...)
        if instance.name not in PRIVILEGED_ROLE_NAMES:
            return
        for user in User.objects.filter(pk__in=pk_set):
            alert_privilege_granted(user, f"el rol «{instance.name}»")
        return
    for name in Group.objects.filter(pk__in=pk_set, name__in=PRIVILEGED_ROLE_NAMES).values_list(
        "name", flat=True
    ):
        alert_privilege_granted(instance, f"el rol «{name}»")


@receiver(pre_save, sender=User)
def remember_superuser_flag(sender, instance, raw=False, **kwargs) -> None:
    if raw or instance.pk is None:
        instance._was_superuser = False
        return
    instance._was_superuser = (
        User.objects.filter(pk=instance.pk).values_list("is_superuser", flat=True).first() or False
    )


@receiver(post_save, sender=User)
def superuser_granted(sender, instance, created, raw=False, **kwargs) -> None:
    if raw or not instance.is_superuser or getattr(instance, "_was_superuser", False):
        return
    alert_privilege_granted(instance, "acceso de superusuario (administración técnica completa)")
