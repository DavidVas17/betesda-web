"""Verificación en dos pasos en el panel: ingreso, activación y gestión.

Flujo de ingreso: la contraseña correcta deja un "ingreso pendiente" en la sesión (sin
iniciarla); la sesión solo se abre cuando se escribe un código válido de la app o un código
de respaldo, dentro de ``TWO_FACTOR_PENDING_MINUTES``.
"""

import time

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.accounts import two_factor
from apps.accounts.alerts import alert_recovery_code_used, alert_two_factor_changed
from apps.accounts.throttle import (
    TOO_MANY_ATTEMPTS,
    clear_failures,
    record_failure,
    seconds_until_allowed,
)
from apps.core.network import client_ip

PENDING_KEY = "two_factor_pending"
PASSWORD_UPGRADE_KEY = "password_upgrade_required"


# --- Ingreso ----------------------------------------------------------------------------------


def start_pending_login(request, user, next_url: str, *, weak_password=False) -> None:
    request.session.cycle_key()
    request.session[PENDING_KEY] = {
        "user": user.pk,
        "backend": getattr(user, "backend", None),
        "at": time.time(),
        "next": next_url,
        "weak_password": weak_password,
    }


def require_password_upgrade(request) -> None:
    request.session[PASSWORD_UPGRADE_KEY] = True


def _pending_user(request):
    data = request.session.get(PENDING_KEY)
    if not data:
        return None, None
    if time.time() - data["at"] > settings.TWO_FACTOR_PENDING_MINUTES * 60:
        request.session.pop(PENDING_KEY, None)
        return None, None
    user = get_user_model().objects.filter(pk=data["user"], is_active=True).first()
    return user, data


class CodeForm(forms.Form):
    code = forms.CharField(
        label="Código de verificación",
        max_length=20,
        help_text="Los 6 números de tu app, o uno de tus códigos de respaldo.",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "autofocus": True,
                "spellcheck": "false",
                "autocapitalize": "off",
            }
        ),
    )


def _wait_error(seconds: int) -> str:
    minutes = max(1, -(-seconds // 60))
    return TOO_MANY_ATTEMPTS % {"minutes": f"{minutes} minuto" + ("s" if minutes != 1 else "")}


@never_cache
@require_http_methods(["GET", "POST"])
def verify(request):
    user, data = _pending_user(request)
    if user is None:
        messages.info(request, "Tu ingreso venció. Escribe de nuevo tu usuario y contraseña.")
        return redirect("panel:login")
    form = CodeForm(request.POST or None)
    key, ip = f"2fa:{user.get_username()}", client_ip(request)
    if request.method == "POST" and form.is_valid():
        wait = seconds_until_allowed(key, ip)
        if wait:
            form.add_error(None, _wait_error(wait))
        else:
            method = two_factor.verify(user, form.cleaned_data["code"])
            if method is None:
                record_failure(key, ip, request=request)
                form.add_error(
                    "code", "El código no es correcto o ya se usó. Intenta con el siguiente."
                )
            else:
                clear_failures(key, ip)
                request.session.pop(PENDING_KEY, None)
                login(request, user, backend=data["backend"] or None)
                if data.get("weak_password"):
                    require_password_upgrade(request)
                if method == "respaldo":
                    alert_recovery_code_used(user, request=request)
                    remaining = two_factor.remaining_recovery_codes(user)
                    messages.warning(
                        request,
                        f"Usaste un código de respaldo. Te quedan {remaining}. "
                        "Si perdiste tu teléfono, configura la verificación de nuevo en Mi cuenta.",
                    )
                next_url = data.get("next") or reverse("panel:dashboard")
                if not url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
                ):
                    next_url = reverse("panel:dashboard")
                return redirect(next_url)
    return render(request, "panel/two_factor_verify.html", {"form": form, "icon": "lock"})


# --- Gestión desde Mi cuenta ------------------------------------------------------------------


class PasswordAndCodeForm(CodeForm):
    password = forms.CharField(
        label="Tu contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    field_order = ("password", "code")

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["code"].widget.attrs.pop("autofocus", None)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("La contraseña no es correcta.")
        return password


def _panel_render(request, template, context, title):
    from .utils import panel_render

    return panel_render(request, template, context, active="account", title=title)


@login_required(login_url="panel:login")
@never_cache
@require_http_methods(["GET", "POST"])
def setup(request):
    """Activar: escanear el QR, confirmar con un código y guardar los códigos de respaldo."""
    if two_factor.is_enabled(request.user):
        return redirect("panel:account")
    device = two_factor.start_setup(request.user)
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        codes = two_factor.confirm_setup(request.user, form.cleaned_data["code"])
        if codes is None:
            form.add_error(
                "code",
                "El código no coincide. Revisa que la hora de tu teléfono sea automática y "
                "usa el código que se ve ahora.",
            )
        else:
            _audit(request, "Activar verificación en dos pasos")
            alert_two_factor_changed(request.user, enabled=True, request=request)
            messages.success(request, "La verificación en dos pasos quedó activa.")
            return _show_recovery_codes(request, codes, first_time=True)
    return _panel_render(
        request,
        "panel/two_factor_setup.html",
        {
            "form": form,
            "otpauth_uri": two_factor.provisioning_uri(device),
            "secret": two_factor.totp.format_secret(device.secret),
            "required": two_factor.is_required(request.user),
        },
        "Verificación en dos pasos",
    )


def _show_recovery_codes(request, codes, *, first_time):
    response = _panel_render(
        request,
        "panel/two_factor_codes.html",
        {"codes": codes, "first_time": first_time},
        "Códigos de respaldo",
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required(login_url="panel:login")
@never_cache
@require_http_methods(["GET", "POST"])
def regenerate_codes(request):
    if not two_factor.is_enabled(request.user):
        return redirect("panel:account")
    form = PasswordAndCodeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        if two_factor.verify(request.user, form.cleaned_data["code"]) != "app":
            form.add_error("code", "Usa el código actual de tu app.")
        else:
            codes = two_factor.regenerate_recovery_codes(request.user)
            _audit(request, "Generar códigos de respaldo nuevos")
            return _show_recovery_codes(request, codes, first_time=False)
    return _panel_render(
        request,
        "panel/two_factor_confirm.html",
        {
            "form": form,
            "form_title": "Generar códigos de respaldo nuevos",
            "form_intro": "Los códigos anteriores dejarán de funcionar.",
            "submit_label": "Generar códigos nuevos",
            "danger": False,
        },
        "Códigos de respaldo",
    )


@login_required(login_url="panel:login")
@never_cache
@require_http_methods(["GET", "POST"])
def disable(request):
    """Desactivar o cambiar de teléfono. Pide contraseña y un código para que nadie la quite
    con una sesión olvidada abierta."""
    if not two_factor.is_enabled(request.user):
        return redirect("panel:account")
    required = two_factor.is_required(request.user)
    form = PasswordAndCodeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        if two_factor.verify(request.user, form.cleaned_data["code"]) is None:
            form.add_error("code", "El código no es correcto o ya se usó.")
        else:
            two_factor.disable(request.user)
            _audit(request, "Desactivar verificación en dos pasos")
            alert_two_factor_changed(request.user, enabled=False, request=request)
            if required:
                messages.info(request, "Configura tu nuevo teléfono para seguir usando el panel.")
                return redirect("panel:two_factor_setup")
            messages.success(request, "La verificación en dos pasos se desactivó.")
            return redirect("panel:account")
    return _panel_render(
        request,
        "panel/two_factor_confirm.html",
        {
            "form": form,
            "form_title": "Cambiar de teléfono" if required else "Desactivar la verificación",
            "form_intro": (
                "Tu rol exige la verificación: después de confirmar, configurarás tu nuevo "
                "teléfono."
                if required
                else "Tu cuenta quedará protegida solo con la contraseña."
            ),
            "submit_label": "Continuar" if required else "Desactivar",
            "danger": not required,
        },
        "Verificación en dos pasos",
    )


def _audit(request, message):
    from .utils import audit

    audit(request, request.user, message=message)


# --- Obligatoria para quien administra ----------------------------------------------------------


class TwoFactorEnforcementMiddleware:
    """Quien administra no usa el panel ni el admin hasta activar la verificación."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._must_setup(request):
            return redirect("panel:two_factor_setup")
        return self.get_response(request)

    @staticmethod
    def _must_setup(request) -> bool:
        path = request.path
        protected = path.startswith("/panel/") or path.startswith(f"/{settings.ADMIN_URL}")
        if not protected or not two_factor.is_required(request.user):
            return False
        allowed = (
            reverse("panel:two_factor_setup"),
            reverse("panel:logout"),
            reverse("panel:login"),
        )
        return path not in allowed and not two_factor.is_enabled(request.user)


class PasswordUpgradeMiddleware:
    """Si la contraseña con la que se entró ya no cumple las reglas, se pide cambiarla antes
    de seguir. Solo afecta a esa sesión; el resto del equipo no nota nada."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.session.get(PASSWORD_UPGRADE_KEY)
            and request.path.startswith(("/panel/", f"/{settings.ADMIN_URL}"))
            and request.path
            not in (
                reverse("panel:password_change"),
                reverse("panel:logout"),
                reverse("panel:two_factor_setup"),
            )
        ):
            messages.warning(
                request,
                "Tu contraseña es más corta o sencilla de lo que pedimos ahora. Elige una nueva "
                "de al menos 10 caracteres para continuar.",
            )
            return redirect("panel:password_change")
        return self.get_response(request)
