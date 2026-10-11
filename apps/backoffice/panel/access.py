from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.views.decorators.cache import never_cache


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


def require_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied
