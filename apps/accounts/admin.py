import contextlib

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.contrib.auth.models import Group

from apps.backoffice.utils import badge, count_message

from .models import KnownDevice, LoginAttempt, User
from .roles import ROLE_NAMES, ROLES_BY_NAME, set_user_roles, user_role_names

# Los grupos son una implementación interna de permisos. El administrador no necesita
# editarlos manualmente y así evitamos que una modificación rompa la política de acceso.
with contextlib.suppress(NotRegistered):
    admin.site.unregister(Group)


class _PanelRolesMixin(forms.Form):
    panel_roles = forms.MultipleChoiceField(
        label="Roles del panel",
        choices=[(name, name) for name in ROLE_NAMES],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=" · ".join(f"{name}: {ROLES_BY_NAME[name].description}" for name in ROLE_NAMES),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["panel_roles"].initial = user_role_names(self.instance)


class AdminUserChangeForm(_PanelRolesMixin, UserChangeForm):
    pass


class AdminUserAddForm(_PanelRolesMixin, AdminUserCreationForm):
    pass


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Gestión de cuentas reservada al superusuario (la única cuenta que entra al admin).

    Los usuarios creados desde aquí son siempre cuentas normales del panel:
    ``is_staff=True`` e ``is_superuser=False``. Su acceso lo dan los roles de ``roles.py``.
    """

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Información personal",
            {"fields": ("first_name", "last_name", "email")},
        ),
        (
            "Acceso al panel",
            {
                "fields": ("is_active", "panel_roles"),
                "description": (
                    "Una cuenta activa entra al panel con los permisos de sus roles. "
                    "Sin roles solo puede ver su propia cuenta."
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
                    "panel_roles",
                ),
            },
        ),
    )
    form = AdminUserChangeForm
    add_form = AdminUserAddForm
    readonly_fields = ("last_login", "date_joined")
    list_display = ("username", "full_name", "email", "roles_label", "active_badge", "last_login")
    list_filter = ("is_active", "groups")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)
    actions = ("activate_users", "deactivate_users")
    save_on_top = True

    @admin.display(description="Nombre", ordering="first_name")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="Roles")
    def roles_label(self, obj):
        return ", ".join(user_role_names(obj)) or "—"

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
        super().save_model(request, obj, form, change)
        set_user_roles(obj, form.cleaned_data.get("panel_roles", []))

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


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Consulta de intentos fallidos. Eliminar los de una persona la desbloquea al instante."""

    list_display = ("username", "ip_address", "created_at")
    list_filter = ("created_at",)
    search_fields = ("username", "ip_address")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(KnownDevice)
class KnownDeviceAdmin(admin.ModelAdmin):
    """Navegadores reconocidos. Eliminar uno hace que el próximo ingreso desde él avise."""

    list_display = ("user", "label", "ip_address", "created_at", "last_seen")
    list_filter = ("last_seen",)
    search_fields = ("user__username", "label", "ip_address")
    readonly_fields = ("user", "key", "label", "ip_address", "created_at", "last_seen")

    def has_add_permission(self, request):
        return False
