from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts import two_factor
from apps.accounts.alerts import alert_password_changed, current_device_key
from apps.accounts.sessions import end_other_sessions
from apps.accounts.throttle import unlock_account

from .access import panel_required
from .forms import (
    PanelAuthenticationForm,
    PanelPasswordResetForm,
    PanelSetPasswordForm,
    ProfileForm,
)
from .security import PASSWORD_UPGRADE_KEY, require_password_upgrade, start_pending_login
from .utils import audit, panel_render


@method_decorator(never_cache, name="dispatch")
class PanelLoginView(LoginView):
    authentication_form = PanelAuthenticationForm
    template_name = "panel/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return reverse("panel:dashboard")

    def form_valid(self, form):
        """Con verificación en dos pasos, la contraseña correcta aún no abre la sesión."""
        user = form.get_user()
        if not two_factor.is_enabled(user):
            response = super().form_valid(form)
            if form.weak_password:
                require_password_upgrade(self.request)
            return response
        start_pending_login(
            self.request, user, self.get_success_url(), weak_password=form.weak_password
        )
        return redirect("panel:two_factor_verify")


def _timeout_hours() -> int:
    return max(1, settings.PASSWORD_RESET_TIMEOUT // 3600)


class PanelPasswordResetView(auth_views.PasswordResetView):
    """Paso 1: pedir el enlace. La respuesta es la misma exista o no la cuenta."""

    form_class = PanelPasswordResetForm
    template_name = "panel/password_reset.html"
    subject_template_name = "panel/email/password_reset_subject.txt"
    # El cuerpo lo arma PanelPasswordResetForm.send_mail con el diseño de los correos.
    success_url = reverse_lazy("panel:password_reset_done")
    extra_email_context = {"timeout_hours": _timeout_hours()}

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "request": self.request}


class PanelPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "panel/password_reset_done.html"
    extra_context = {"timeout_hours": _timeout_hours(), "icon": "inbox"}


class PanelPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """Paso 2: elegir la contraseña nueva desde el enlace del correo."""

    form_class = PanelSetPasswordForm
    template_name = "panel/password_reset_confirm.html"
    success_url = reverse_lazy("panel:login")
    post_reset_login = False

    def form_valid(self, form):
        response = super().form_valid(form)
        audit(self.request, form.user, message="Restablecer contraseña por correo", actor=form.user)
        alert_password_changed(form.user, request=self.request)
        # Quien recuperó su contraseña ya demostró ser la dueña del correo: se quita el
        # bloqueo por intentos fallidos para que pueda entrar de inmediato.
        unlock_account(form.user.get_username())
        messages.success(
            self.request, "Tu contraseña cambió. Ya puedes ingresar con la nueva contraseña."
        )
        return response


@panel_required()
@require_POST
def logout_others(request):
    """Cierra la sesión en todos los demás navegadores de esta cuenta."""
    closed = end_other_sessions(request)
    audit(request, request.user, message=f"Cerrar sesión en otros dispositivos ({closed}).")
    messages.success(
        request,
        f"Cerramos {closed} sesión{'es' if closed != 1 else ''} en otros dispositivos."
        if closed
        else "No había otras sesiones abiertas.",
    )
    return redirect("panel:account")


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
        user.save(update_fields=[name for name in form.fields if name in form.cleaned_data])
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
            "two_factor_enabled": two_factor.is_enabled(request.user),
            "two_factor_required": two_factor.is_required(request.user),
            "recovery_codes_left": two_factor.remaining_recovery_codes(request.user),
            "devices": request.user.known_devices.all()[:6],
            "current_device": current_device_key(request),
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
        alert_password_changed(user, request=request)
        request.session.pop(PASSWORD_UPGRADE_KEY, None)
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
