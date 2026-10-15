from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm

from apps.accounts.throttle import ThrottledLoginMixin


class ThrottledAdminAuthenticationForm(ThrottledLoginMixin, AdminAuthenticationForm):
    """El login de la administración técnica tiene el mismo freno que el del panel."""


class BetesdaAdminSite(admin.AdminSite):
    """Administración técnica: el admin estándar de Django, reservado al superusuario.

    El trabajo diario del equipo ocurre en el panel (/panel/), que tiene su propio tablero,
    permisos por rol y diseño. Aquí no se mantiene un tablero ni un tema aparte.
    """

    site_header = "Betesda Rosa de Sarón · Administración técnica"
    site_title = "Administración técnica"
    index_title = "Mantenimiento del sitio"
    site_url = "/"
    empty_value_display = "—"
    login_form = ThrottledAdminAuthenticationForm

    def has_permission(self, request):
        """La administración técnica es exclusiva del superusuario.

        Django permite por defecto la entrada a cualquier cuenta con ``is_staff``. Todas las
        cuentas del panel son ``is_staff``, así que sin esta regla cualquier integrante del
        equipo podría escribir la dirección del admin y saltarse los permisos del panel.
        """
        user = request.user
        return bool(user.is_active and user.is_superuser)
