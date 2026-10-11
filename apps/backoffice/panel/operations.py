from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.content import INSTITUTION
from apps.core.models import SiteConfiguration

from .access import panel_required, require_superuser
from .forms import SiteSettingsForm, TeamUserCreateForm, TeamUserEditForm
from .utils import audit, paginate, pagination_query, panel_render

User = get_user_model()


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
            for key in ("slogan", "phone", "email", "address", "facebook_url", "map_url")
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


@panel_required()
@require_GET
def user_list(request):
    require_superuser(request)
    query = request.GET.get("q", "").strip()[:200]
    users = User.objects.filter(is_superuser=False).order_by("-is_active", "username", "pk")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    return panel_render(
        request,
        "panel/users.html",
        {
            "page_obj": paginate(request, users, 15),
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
    require_superuser(request)
    user = get_object_or_404(User, pk=pk, is_superuser=False) if pk is not None else None
    form_class = TeamUserEditForm if user else TeamUserCreateForm
    form = form_class(request.POST if request.method == "POST" else None, instance=user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            audit(
                request,
                saved,
                flag=CHANGE if user else ADDITION,
                message="Cuenta del equipo actualizada." if user else "Cuenta del equipo creada.",
            )
        messages.success(request, "Cuenta guardada correctamente.")
        return redirect("panel:user_edit", pk=saved.pk)
    return panel_render(
        request,
        "panel/form.html",
        {
            "form": form,
            "form_title": "Editar cuenta" if user else "Agregar persona al equipo",
            "form_intro": (
                "Esta cuenta podrá gestionar contenido y atender solicitudes de la comunidad."
            ),
            "cancel_url": reverse("panel:user_list"),
            "submit_label": "Guardar cuenta",
            "can_save": True,
            "object": user,
            "password_url": reverse("panel:user_password", args=[pk]) if user else "",
            "delete_url": reverse("panel:user_delete", args=[pk]) if user else "",
        },
        active="users",
        title="Editar usuario" if user else "Nuevo usuario",
    )


@panel_required()
@require_http_methods(["GET", "POST"])
def user_create(request):
    return _team_form(request)


@panel_required()
@require_http_methods(["GET", "POST"])
def user_edit(request, pk):
    return _team_form(request, pk)


@panel_required()
@require_http_methods(["GET", "POST"])
def user_delete(request, pk):
    require_superuser(request)
    user = get_object_or_404(User, pk=pk, is_superuser=False)
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


@panel_required()
@require_http_methods(["GET", "POST"])
def user_password(request, pk):
    require_superuser(request)
    user = get_object_or_404(User, pk=pk, is_superuser=False)
    form = SetPasswordForm(user, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.save(update_fields=("password",))
        audit(request, user, message="Contraseña de cuenta restablecida.")
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


@panel_required()
@require_GET
def activity(request):
    require_superuser(request)
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
        },
        active="activity",
        title="Actividad",
        subtitle="Un registro de los cambios realizados por el equipo.",
    )
