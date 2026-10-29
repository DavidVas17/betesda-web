from django.contrib import admin, messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls import reverse


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

    def has_permission(self, request):
        """La administración técnica es exclusiva del superusuario.

        Django permite por defecto la entrada a cualquier cuenta con ``is_staff``. Todas las
        cuentas del panel son ``is_staff``, así que sin esta regla cualquier integrante del
        equipo podría escribir la dirección del admin y saltarse los permisos del panel.
        """
        user = request.user
        return bool(user.is_active and user.is_superuser)

    def login(self, request, extra_context=None):
        """Se ingresa por el panel: así el admin tiene el mismo freno de intentos y la misma
        verificación en dos pasos, sin un segundo formulario que proteger."""
        if request.user.is_authenticated:
            if self.has_permission(request):
                return redirect(request.GET.get("next") or reverse("admin:index"))
            messages.error(request, "La administración técnica es solo para el superusuario.")
            return redirect("panel:dashboard")
        return redirect_to_login(
            request.GET.get("next") or reverse("admin:index"), reverse("panel:login")
        )
