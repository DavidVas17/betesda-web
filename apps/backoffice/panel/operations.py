from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts import two_factor
from apps.accounts.alerts import (
    alert_account_created,
    alert_password_changed,
    alert_two_factor_changed,
)
from apps.accounts.models import LoginAttempt
from apps.accounts.roles import PRIVILEGED_ROLE_NAMES, ROLE_NAMES
from apps.contacts.models import ContactMessage
from apps.core.content import INSTITUTION
from apps.core.models import SiteConfiguration

from .access import panel_required
from .forms import SiteSettingsForm, TeamUserCreateForm, TeamUserEditForm
from .security import recent_auth_required
from .utils import audit, paginate, pagination_query, panel_render

User = get_user_model()
TEAM_PERMISSION = "accounts.manage_team"


def _role_names(member) -> list[str]:
    # Usa los grupos ya precargados con prefetch_related para no consultar por fila.
    names = {group.name for group in member.groups.all()}
    return [name for name in ROLE_NAMES if name in names]


def can_manage_member(actor, member) -> bool:
    """El superusuario gestiona a todos; Administración no gestiona a sus pares.

    Así una persona con Administración de la iglesia no puede quitarle el acceso,
    cambiarle la contraseña ni borrar a otra con su mismo nivel. Su propia cuenta la
    edita con roles y estado bloqueados (ver ``TeamRolesMixin``).
    """
    if member.is_superuser:
        return False
    if actor.is_superuser or member.pk == actor.pk:
        return True
    return not (set(_role_names(member)) & PRIVILEGED_ROLE_NAMES)


def _team_member(request, pk, *, allow_self=True):
    member = get_object_or_404(User.objects.prefetch_related("groups"), pk=pk)
    if not can_manage_member(request.user, member):
        raise PermissionDenied
    if not allow_self and member.pk == request.user.pk:
        raise PermissionDenied
    return member


@panel_required(
    ("core.view_siteconfiguration", "core.add_siteconfiguration", "core.change_siteconfiguration")
)
@require_http_methods(["GET", "POST"])
def settings(request):
    configuration = SiteConfiguration.objects.first()
    permission = "core.change_siteconfiguration" if configuration else "core.add_siteconfiguration"
    can_save = request.user.has_perm(permission)
    initial = {
        "institution_name": INSTITUTION["name"],
        **{
            key: INSTITUTION[key]
            for key in (
                "slogan",
                "phone",
                "email",
                "address",
                "facebook_url",
                "map_url",
                "mission",
                "vision",
                "purpose",
                "history",
            )
        },
    }
    if request.method == "POST" and not can_save:
        raise PermissionDenied
    form = SiteSettingsForm(
        request.POST if request.method == "POST" else None,
        instance=configuration,
        initial=initial if configuration is None else None,
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                if configuration is None:
                    # Competing first saves use the same key and cannot create two configurations.
                    configuration = form.save(commit=False)
                    configuration.pk = 1
                    configuration.save(force_insert=True)
                else:
                    configuration = form.save()
                audit(
                    request,
                    configuration,
                    flag=ADDITION if permission.startswith("core.add_") else CHANGE,
                    message="Información de la iglesia actualizada.",
                )
        except IntegrityError:
            messages.warning(
                request,
                "Otra persona guardó la configuración. Revisa los datos antes de volver a guardar.",
            )
            return redirect("panel:settings")
        messages.success(
            request, "Información actualizada. Los cambios ya se muestran en el sitio."
        )
        return redirect("panel:settings")
    if not can_save:
        for field in form.fields.values():
            field.disabled = True
    return panel_render(
        request,
        "panel/form.html",
        {
            "form": form,
            "form_title": "Información de la iglesia",
            "form_intro": "Mantén al día los datos de contacto que ve nuestra comunidad.",
            "cancel_url": reverse("panel:dashboard"),
            "submit_label": "Guardar información",
            "can_save": can_save,
        },
        active="settings",
        title="Configuración",
        subtitle="Los datos generales que se comparten en el sitio web.",
    )


@panel_required(TEAM_PERMISSION)
@require_GET
def user_list(request):
    query = request.GET.get("q", "").strip()[:200]
    users = (
        User.objects.filter(is_superuser=False)
        .prefetch_related("groups")
        .order_by("-is_active", "username", "pk")
    )
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    page_obj = paginate(request, users, 15)
    for member in page_obj:
        member.roles_label = ", ".join(_role_names(member)) or "Sin roles"
        member.can_manage = can_manage_member(request.user, member)
    return panel_render(
        request,
        "panel/users.html",
        {
            "page_obj": page_obj,
            "query": query,
            "create_url": reverse("panel:user_create"),
            "can_change": True,
            "can_delete": True,
            "pagination_query": pagination_query(request),
        },
        active="users",
        title="Usuarios",
        subtitle="Las personas que colaboran en la administración de la iglesia.",
    )


def _team_form(request, pk=None):
    user = _team_member(request, pk) if pk is not None else None
    was_active = bool(user and user.is_active)
    form_class = TeamUserEditForm if user else TeamUserCreateForm
    form = form_class(
        request.POST if request.method == "POST" else None, instance=user, actor=request.user
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            released = 0
            if was_active and not saved.is_active:
                # Quien ya no está en el equipo no debe quedar como responsable de nadie.
                released = ContactMessage.objects.filter(
                    assigned_to=saved,
                    status__in=(ContactMessage.Status.NEW, ContactMessage.Status.IN_PROGRESS),
                ).update(assigned_to=None)
            roles = ", ".join(form.cleaned_data["roles"]) or "sin roles"
            summary = "Cuenta del equipo actualizada" if user else "Cuenta del equipo creada"
            audit(
                request,
                saved,
                flag=CHANGE if user else ADDITION,
                message=f"{summary}. Roles: {roles}."
                + (f" Solicitudes liberadas: {released}." if released else ""),
            )
        if user is None and not set(form.cleaned_data["roles"]) & PRIVILEGED_ROLE_NAMES:
            # Las cuentas con privilegios ya generan su propio aviso al recibir el rol.
            alert_account_created(request.user, saved, form.cleaned_data["roles"])
        messages.success(request, "Cuenta guardada correctamente.")
        return redirect("panel:user_edit", pk=saved.pk)
    return panel_render(
        request,
        "panel/form.html",
        {
            "form": form,
            "form_title": "Editar cuenta" if user else "Agregar persona al equipo",
            "form_intro": (
                "Elige los roles según lo que esta persona va a manejar. Puedes combinar varios."
            ),
            "cancel_url": reverse("panel:user_list"),
            "submit_label": "Guardar cuenta",
            "can_save": True,
            "object": user,
            "password_url": (
                reverse("panel:user_password", args=[pk])
                if user and user.pk != request.user.pk
                else ""
            ),
            "two_factor_reset_url": (
                reverse("panel:user_two_factor_reset", args=[pk])
                if user and user.pk != request.user.pk and two_factor.is_enabled(user)
                else ""
            ),
            "delete_url": (
                reverse("panel:user_delete", args=[pk])
                if user and user.pk != request.user.pk
                else ""
            ),
        },
        active="users",
        title="Editar usuario" if user else "Nuevo usuario",
    )


@panel_required(TEAM_PERMISSION)
@recent_auth_required
@require_http_methods(["GET", "POST"])
def user_create(request):
    return _team_form(request)


@panel_required(TEAM_PERMISSION)
@recent_auth_required
@require_http_methods(["GET", "POST"])
def user_edit(request, pk):
    return _team_form(request, pk)


@panel_required(TEAM_PERMISSION)
@recent_auth_required
@require_http_methods(["GET", "POST"])
def user_two_factor_reset(request, pk):
    """Para quien perdió su teléfono y sus códigos: quita su verificación para configurarla
    de nuevo. Mismas reglas que editar la cuenta (nadie la quita a un par ni a sí mismo)."""
    user = _team_member(request, pk, allow_self=False)
    if request.method == "POST":
        two_factor.disable(user)
        audit(request, user, message="Verificación en dos pasos restablecida.")
        alert_two_factor_changed(user, enabled=False, by=request.user, request=request)
        messages.success(
            request,
            "Listo. Al ingresar, esta persona configurará la verificación de nuevo"
            + (" (es obligatoria para su rol)." if two_factor.is_required(user) else "."),
        )
        return redirect("panel:user_edit", pk=pk)
    return panel_render(
        request,
        "panel/delete.html",
        {
            "object": user,
            "confirm_heading": "Restablecer verificación en dos pasos",
            "confirm_question": "¿Restablecer la verificación en dos pasos de esta cuenta?",
            "cancel_url": reverse("panel:user_edit", args=[pk]),
            "delete_message": (
                "Úsalo solo si esta persona perdió su teléfono y sus códigos de respaldo. "
                "Confirma su identidad en persona o por teléfono antes de continuar."
            ),
            "submit_label": "Restablecer verificación",
        },
        active="users",
        title="Restablecer verificación",
    )


@panel_required(TEAM_PERMISSION)
@recent_auth_required
@require_http_methods(["GET", "POST"])
def user_delete(request, pk):
    user = _team_member(request, pk, allow_self=False)
    if request.method == "POST":
        try:
            with transaction.atomic():
                audit(request, user, flag=DELETION, message="Cuenta del equipo eliminada.")
                user.delete()
        except ProtectedError:
            messages.error(
                request,
                "Esta persona es autora de noticias. "
                "Desactiva su cuenta para conservar el contenido.",
            )
            return redirect("panel:user_edit", pk=pk)
        messages.success(request, "Cuenta eliminada correctamente.")
        return redirect("panel:user_list")
    return panel_render(
        request,
        "panel/delete.html",
        {
            "object": user,
            "object_label": "Cuenta",
            "cancel_url": reverse("panel:user_edit", args=[pk]),
            "delete_message": (
                "Esta persona perderá el acceso al panel. "
                "También puedes desactivar la cuenta para conservarla."
            ),
        },
        active="users",
        title="Eliminar usuario",
    )


@panel_required(TEAM_PERMISSION)
@recent_auth_required
@require_http_methods(["GET", "POST"])
def user_password(request, pk):
    # La contraseña propia se cambia desde "Mi cuenta", pidiendo la actual.
    user = _team_member(request, pk, allow_self=False)
    form = SetPasswordForm(user, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.save(update_fields=("password",))
        audit(request, user, message="Contraseña de cuenta restablecida.")
        alert_password_changed(user, by=request.user, request=request)
        messages.success(request, "Contraseña actualizada correctamente.")
        return redirect("panel:user_edit", pk=pk)
    return panel_render(
        request,
        "panel/form.html",
        {
            "form": form,
            "form_title": f"Nueva contraseña para {user.username}",
            "form_intro": "Comparte la nueva contraseña con esta persona por un medio privado.",
            "cancel_url": reverse("panel:user_edit", args=[pk]),
            "submit_label": "Actualizar contraseña",
            "can_save": True,
        },
        active="users",
        title="Restablecer contraseña",
    )


def _recent_failed_logins(days: int = 7):
    """Intentos fallidos de la última semana, agrupados por cuenta y conexión."""
    since = timezone.now() - timedelta(days=days)
    return (
        LoginAttempt.objects.filter(created_at__gte=since)
        .values("username", "ip_address")
        .annotate(total=Count("pk"), last=Max("created_at"))
        .order_by("-last")[:15]
    )


@panel_required("accounts.view_activity")
@require_GET
def activity(request):
    query = request.GET.get("q", "").strip()[:200]
    entries = LogEntry.objects.select_related("user", "content_type").order_by(
        "-action_time", "-pk"
    )
    if query:
        entries = entries.filter(
            Q(object_repr__icontains=query)
            | Q(change_message__icontains=query)
            | Q(user__username__icontains=query)
        )
    return panel_render(
        request,
        "panel/activity.html",
        {
            "page_obj": paginate(request, entries, 20),
            "query": query,
            "pagination_query": pagination_query(request),
            "failed_logins": _recent_failed_logins(),
        },
        active="activity",
        title="Actividad",
        subtitle="Un registro de los cambios realizados por el equipo.",
    )
