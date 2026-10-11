from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .access import panel_required
from .forms import PanelAuthenticationForm, ProfileForm
from .utils import audit, panel_render


@method_decorator(never_cache, name="dispatch")
class PanelLoginView(LoginView):
    authentication_form = PanelAuthenticationForm
    template_name = "panel/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return reverse("panel:dashboard")


@never_cache
@require_POST
def logout_view(request):
    logout(request)
    return redirect("panel:login")


@panel_required()
@require_http_methods(["GET", "POST"])
def account(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.save(update_fields=("first_name", "last_name", "email"))
        audit(request, user, message="Actualizar perfil personal")
        messages.success(request, "Tu información se actualizó correctamente.")
        return redirect("panel:account")
    return panel_render(
        request,
        "panel/account.html",
        {
            "form": form,
            "current_user": request.user,
            "password_url": reverse("panel:password_change"),
        },
        active="account",
        title="Mi cuenta",
        subtitle="Actualiza tus datos personales y cuida el acceso a tu cuenta.",
    )


@panel_required()
@require_http_methods(["GET", "POST"])
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.save(update_fields=("password",))
        update_session_auth_hash(request, user)
        audit(request, user, message="Cambiar contraseña personal")
        messages.success(request, "Tu contraseña cambió. Tu sesión sigue abierta.")
        return redirect("panel:account")
    return panel_render(
        request,
        "panel/form.html",
        {
            "form": form,
            "form_title": "Cambiar mi contraseña",
            "form_intro": "Escribe tu contraseña actual y elige una nueva contraseña segura.",
            "cancel_url": reverse("panel:account"),
            "submit_label": "Actualizar contraseña",
            "can_save": True,
        },
        active="account",
        title="Cambiar contraseña",
    )
