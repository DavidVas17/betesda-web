from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from apps.backoffice.utils import badge, count_message

from .models import User

# Los grupos son una implementación interna de permisos. El administrador no necesita
# editarlos manualmente y así evitamos que una modificación rompa la política de acceso.
try:
    admin.site.unregister(Group)
except NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Gestión simple de cuentas reservada al superusuario principal.

    Los usuarios creados desde aquí son siempre cuentas normales del BackOffice:
    ``is_staff=True``, ``is_superuser=False`` y rol editorial. Los permisos reales del
    contenido se asignan automáticamente mediante los grupos gestionados en ``roles.py``.
    """

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Información personal",
            {"fields": ("first_name", "last_name", "email")},
        ),
        (
            "Acceso al BackOffice",
            {
                "fields": ("is_active",),
                "description": (
                    "Una cuenta activa puede entrar al panel y gestionar el contenido del sitio."
                ),
            },
        ),
        (
            "Registro",
            {"fields": ("last_login", "date_joined"), "classes": ("collapse",)},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "email",
                    "is_active",
                ),
            },
        ),
    )
    readonly_fields = ("last_login", "date_joined")
    list_display = ("username", "full_name", "email", "active_badge", "last_login")
    list_filter = ("is_active",)
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)
    actions = ("activate_users", "deactivate_users")
    save_on_top = True

    @admin.display(description="Nombre", ordering="first_name")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="Estado", ordering="is_active")
    def active_badge(self, obj):
        return badge("Activo", "ok") if obj.is_active else badge("Desactivado", "neutral")

    def get_queryset(self, request):
        # El superusuario raíz se administra por bootstrap/CLI y no desde esta pantalla.
        return super().get_queryset(request).exclude(is_superuser=True)

    # --- Solo el superusuario puede administrar cuentas -------------------------
    def has_module_permission(self, request) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request, obj=None) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def has_add_permission(self, request) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def has_change_permission(self, request, obj=None) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def save_model(self, request, obj, form, change) -> None:
        # Cualquier cuenta gestionada aquí es una cuenta normal de BackOffice.
        obj.is_staff = True
        obj.is_superuser = False
        obj.role = User.Role.EDITOR
        super().save_model(request, obj, form, change)

    @admin.action(description="Activar cuentas seleccionadas", permissions=["change"])
    def activate_users(self, request, queryset) -> None:
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"{count_message(updated, 'cuenta activada', 'cuentas activadas')}.",
            messages.SUCCESS,
        )

    @admin.action(description="Desactivar cuentas seleccionadas", permissions=["change"])
    def deactivate_users(self, request, queryset) -> None:
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"{count_message(updated, 'cuenta desactivada', 'cuentas desactivadas')}.",
            messages.WARNING if updated else messages.INFO,
        )
