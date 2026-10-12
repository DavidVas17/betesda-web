"""Roles del panel y sus permisos, definidos en código.

Cada rol es un ``Group`` de Django cuyos permisos se reescriben en cada despliegue
(``ensure_role_groups`` corre después de ``migrate`` y en ``setup_roles``), así la política de
acceso nunca depende de clics manuales. Una persona puede tener varios roles: sus permisos
se suman.

La administración técnica (``/admin/``) no es un rol: queda reservada al superusuario.
"""

from dataclasses import dataclass

from django.contrib.auth.models import Group, Permission
from django.db.models import Q

_FULL = ("add", "change", "delete", "view")
_EDIT = ("add", "change", "view")


@dataclass(frozen=True)
class Role:
    key: str
    name: str
    description: str
    permissions: dict[str, tuple[str, ...]]


_CONTENT_FULL: dict[str, tuple[str, ...]] = {
    "events.event": (*_FULL, "publish"),
    "news.post": (*_FULL, "publish"),
    "gallery.album": (*_FULL, "publish"),
    "gallery.photo": _FULL,
}

CHURCH_ADMIN = Role(
    key="church_admin",
    name="Administración de la iglesia",
    description=(
        "Todo el panel: contenido, mensajes, configuración del sitio, usuarios y bitácora."
    ),
    permissions={
        **_CONTENT_FULL,
        "contacts.contactmessage": ("view", "change", "delete", "export"),
        # Existe una sola configuración y su vista impide eliminarla.
        "core.siteconfiguration": ("add", "change", "view"),
        "core.ministry": _FULL,
        "core.churchvalue": _FULL,
        "accounts.user": ("manage_team", "view_activity"),
    },
)

COORDINATOR = Role(
    key="coordinator",
    name="Coordinación de contenido",
    description="Crea, publica y elimina eventos, noticias y álbumes.",
    permissions=_CONTENT_FULL,
)

COLLABORATOR = Role(
    key="collaborator",
    name="Colaboración de contenido",
    description=(
        "Crea borradores de eventos, noticias y álbumes, y edita solo los suyos mientras "
        "no estén publicados. No publica ni elimina."
    ),
    permissions={
        "events.event": _EDIT,
        "news.post": _EDIT,
        "gallery.album": _EDIT,
        "gallery.photo": _EDIT,
    },
)

GALLERY = Role(
    key="gallery",
    name="Galería",
    description="Crea álbumes, sube fotografías, y publica o elimina álbumes.",
    permissions={
        "gallery.album": (*_FULL, "publish"),
        "gallery.photo": _FULL,
    },
)

CARE = Role(
    key="care",
    name="Atención y oración",
    description="Lee y da seguimiento a las peticiones de oración y mensajes de contacto.",
    permissions={"contacts.contactmessage": ("view", "change")},
)

READ_ONLY = Role(
    key="read_only",
    name="Solo lectura",
    description="Consulta eventos, noticias y galería sin poder cambiar nada.",
    permissions={
        "events.event": ("view",),
        "news.post": ("view",),
        "gallery.album": ("view",),
        "gallery.photo": ("view",),
    },
)

ROLES: tuple[Role, ...] = (CHURCH_ADMIN, COORDINATOR, COLLABORATOR, GALLERY, CARE, READ_ONLY)
ROLE_NAMES: tuple[str, ...] = tuple(role.name for role in ROLES)
ROLES_BY_NAME = {role.name: role for role in ROLES}

# Roles que solo el superusuario puede asignar o quitar: quien los tiene gestiona al equipo,
# y nadie debe poder crear a otra persona con su mismo nivel desde el panel.
PRIVILEGED_ROLE_NAMES = frozenset({CHURCH_ADMIN.name})


def _codename(action: str, model_name: str) -> str:
    # "view", "publish"… se completan con el modelo ("publish_post"); un nombre que ya
    # trae guion bajo ("manage_team") es el codename completo de un permiso propio.
    return action if "_" in action else f"{action}_{model_name}"


def _permission_query(spec: dict[str, tuple[str, ...]]) -> Q:
    query = Q(pk__in=[])
    for label, actions in spec.items():
        app_label, model_name = label.split(".")
        for action in actions:
            query |= Q(content_type__app_label=app_label, codename=_codename(action, model_name))
    return query


def role_permission_codenames(role: Role) -> set[str]:
    """``app.codename`` de cada permiso del rol, útil para pruebas y revisiones."""
    result = set()
    for label, actions in role.permissions.items():
        app_label, model_name = label.split(".")
        result.update(f"{app_label}.{_codename(action, model_name)}" for action in actions)
    return result


def ensure_role_groups() -> None:
    """Crea los grupos y deja sus permisos exactamente como se definen arriba."""
    for role in ROLES:
        group, _ = Group.objects.get_or_create(name=role.name)
        group.permissions.set(Permission.objects.filter(_permission_query(role.permissions)))


def role_groups():
    """Los grupos de rol, en el orden en que se muestran en el panel."""
    ensure_role_groups_exist()
    groups = {group.name: group for group in Group.objects.filter(name__in=ROLE_NAMES)}
    return [groups[name] for name in ROLE_NAMES]


def ensure_role_groups_exist() -> None:
    if Group.objects.filter(name__in=ROLE_NAMES).count() < len(ROLE_NAMES):
        ensure_role_groups()


def user_role_names(user) -> list[str]:
    """Nombres de los roles de una cuenta, en el orden oficial."""
    names = set(user.groups.filter(name__in=ROLE_NAMES).values_list("name", flat=True))
    return [name for name in ROLE_NAMES if name in names]


def set_user_roles(user, names) -> None:
    """Deja a la cuenta exactamente con los roles indicados, sin tocar otros grupos."""
    wanted = set(names)
    unknown = wanted - set(ROLE_NAMES)
    if unknown:
        raise ValueError(f"Roles desconocidos: {', '.join(sorted(unknown))}")
    groups = role_groups()
    user.groups.remove(*[group for group in groups if group.name not in wanted])
    user.groups.add(*[group for group in groups if group.name in wanted])
