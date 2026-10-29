from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.views.decorators.cache import never_cache

from apps.events.models import Event
from apps.gallery.models import Album, Photo
from apps.news.models import Post


def panel_required(permission=None):
    """Exige una cuenta activa del equipo y, opcionalmente, uno de los permisos."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path(), reverse("panel:login"))
            if not (user.is_active and user.is_staff):
                raise PermissionDenied
            permissions = (permission,) if isinstance(permission, str) else permission
            if permissions and not any(user.has_perm(value) for value in permissions):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return never_cache(wrapped)

    return decorator


def require_permission(request, permission):
    if not request.user.has_perm(permission):
        raise PermissionDenied


# --- Contenido: quién publica y quién edita cada elemento ---------------------------


def _perm(model, action):
    return f"{model._meta.app_label}.{action}_{model._meta.model_name}"


def can_publish(user, model) -> bool:
    """Publicar, retirar, archivar o destacar es una decisión aparte de editar."""
    return user.has_perm(_perm(model, "publish"))


def is_owner(user, obj) -> bool:
    if isinstance(obj, Post):
        return obj.author_id == user.pk
    if isinstance(obj, (Event, Album)):
        return obj.created_by_id is not None and obj.created_by_id == user.pk
    return False


def is_draft(obj) -> bool:
    if isinstance(obj, Post):
        return obj.status == Post.Status.DRAFT
    return not obj.is_published


def can_edit(user, obj) -> bool:
    """Puede modificar este elemento concreto.

    Quien puede publicar edita cualquier elemento. Quien solo puede editar (Colaboración)
    trabaja únicamente sobre sus propios borradores: así nada llega al sitio, ni cambia
    algo que ya está publicado, sin que alguien con permiso de publicar lo revise.
    """
    if isinstance(obj, Photo):
        return user.has_perm("gallery.change_photo") and can_edit(user, obj.album)
    model = type(obj)
    if not user.has_perm(_perm(model, "change")):
        return False
    return can_publish(user, model) or (is_owner(user, obj) and is_draft(obj))


def require_edit(request, obj) -> None:
    if not can_edit(request.user, obj):
        raise PermissionDenied


def require_publish(request, model) -> None:
    if not can_publish(request.user, model):
        raise PermissionDenied
