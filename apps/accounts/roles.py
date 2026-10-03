"""Roles internos del BackOffice y permisos operativos.

Los dos roles conservados en el modelo reciben el mismo acceso al contenido del sitio.
La administración de cuentas se reserva al superusuario mediante ``CustomUserAdmin``.
Los grupos se siguen gestionando en código para que el despliegue sea reproducible.
"""

from django.contrib.auth.models import Group, Permission
from django.db.models import Q

ADMIN_GROUP = "Administradores"
EDITOR_GROUP = "Editores de contenido"

ROLE_GROUPS = {
    "ADMIN": ADMIN_GROUP,
    "EDITOR": EDITOR_GROUP,
}

_FULL = ("add", "change", "delete", "view")

# Un usuario normal del BackOffice puede gestionar todo el contenido. Las cuentas de
# usuario no aparecen aquí a propósito: solo el superusuario puede administrarlas.
_BACKOFFICE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "events.event": _FULL,
    "news.post": _FULL,
    "gallery.album": _FULL,
    "gallery.photo": _FULL,
    # Los mensajes llegan desde el sitio público; no se crean manualmente en el panel.
    "contacts.contactmessage": ("view", "change", "delete"),
    # Existe una sola configuración y su ModelAdmin impide eliminarla.
    "core.siteconfiguration": ("add", "change", "view"),
}

ROLE_PERMISSIONS: dict[str, dict[str, tuple[str, ...]]] = {
    ADMIN_GROUP: _BACKOFFICE_PERMISSIONS,
    EDITOR_GROUP: _BACKOFFICE_PERMISSIONS,
}


def ensure_role_groups() -> None:
    """Crea los grupos y deja sus permisos exactamente como se definen arriba."""
    for group_name, spec in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        query = Q()
        for label, actions in spec.items():
            app_label, model_name = label.split(".")
            for action in actions:
                query |= Q(content_type__app_label=app_label, codename=f"{action}_{model_name}")
        group.permissions.set(Permission.objects.filter(query))


def sync_user_role(user) -> None:
    """Mantiene a cada cuenta de BackOffice en el grupo correspondiente a su rol."""
    wanted_name = ROLE_GROUPS.get(user.role)
    groups = {g.name: g for g in Group.objects.filter(name__in=ROLE_GROUPS.values())}
    if len(groups) < len(ROLE_GROUPS):
        ensure_role_groups()
        groups = {g.name: g for g in Group.objects.filter(name__in=ROLE_GROUPS.values())}

    stale = [group for name, group in groups.items() if name != wanted_name]
    if stale:
        user.groups.remove(*stale)
    if wanted_name:
        user.groups.add(groups[wanted_name])
