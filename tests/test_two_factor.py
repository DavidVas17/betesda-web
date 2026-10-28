"""Verificación en dos pasos (TOTP + códigos de respaldo)."""

import base64
import time

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.urls import reverse

from apps.accounts import totp, two_factor
from apps.accounts.models import RecoveryCode, TwoFactorDevice
from apps.accounts.roles import CARE, CHURCH_ADMIN, set_user_roles

pytestmark = pytest.mark.django_db
User = get_user_model()
LOGIN = reverse("panel:login")
VERIFY = reverse("panel:two_factor_verify")
SETUP = reverse("panel:two_factor_setup")


@pytest.fixture(autouse=True)
def deliver_now(monkeypatch, settings):
    settings.LOGIN_RATE_LIMIT = (3, 50, 900)
    monkeypatch.setattr("apps.accounts.alerts.transaction.on_commit", lambda func: func())


@pytest.fixture
def maria():
    user = User.objects.create_user(
        "maria", "maria@example.com", "clave-correcta-2026", is_staff=True
    )
    set_user_roles(user, [CARE.name])
    return user


def enable(user):
    device = two_factor.start_setup(user)
    codes = two_factor.confirm_setup(user, totp.code_at(device.secret, totp.current_step()))
    device.refresh_from_db()
    device.last_step = 0  # el código de la activación no bloquea el primer ingreso de prueba
    device.save()
    return device, codes


def now_code(device, offset=0):
    return totp.code_at(device.secret, totp.current_step() + offset)


def password_step(client, user="maria", password="clave-correcta-2026"):
    return client.post(LOGIN, {"username": user, "password": password}, REMOTE_ADDR="203.0.113.5")


# --- TOTP ---------------------------------------------------------------------------------------


def test_totp_matches_rfc_6238_vectors():
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert totp.code_at(secret, 59 // 30) == "287082"
    assert totp.code_at(secret, 1111111109 // 30) == "081804"
    assert totp.code_at(secret, 2000000000 // 30) == "279037"


def test_codes_from_neighbour_intervals_are_accepted_but_not_reused():
    secret = totp.generate_secret()
    now = time.time()
    step = totp.current_step(now)

    assert totp.matching_step(secret, totp.code_at(secret, step - 1), at=now) == step - 1
    assert totp.matching_step(secret, totp.code_at(secret, step + 2), at=now) is None
    assert totp.matching_step(secret, totp.code_at(secret, step), last_step=step, at=now) is None


def test_provisioning_uri_for_apps():
    uri = totp.provisioning_uri("ABCDEF", "maria", "Betesda Rosa de Sarón")
    assert uri.startswith("otpauth://totp/Betesda%20Rosa%20de%20Sar%C3%B3n%3Amaria?")
    assert "secret=ABCDEF" in uri


# --- Ingreso --------------------------------------------------------------------------------------


def test_without_two_factor_login_is_unchanged(client, maria):
    response = password_step(client)

    assert response.status_code == 302 and response["Location"] == reverse("panel:dashboard")
    assert "_auth_user_id" in client.session


def test_password_alone_does_not_open_the_session(client, maria):
    device, _ = enable(maria)

    response = password_step(client)

    assert response["Location"] == VERIFY
    assert "_auth_user_id" not in client.session
    assert client.get(reverse("panel:dashboard")).status_code == 302

    response = client.post(VERIFY, {"code": now_code(device)})
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(maria.pk)


def test_wrong_code_keeps_the_door_closed(client, maria):
    enable(maria)
    password_step(client)

    response = client.post(VERIFY, {"code": "000000"})

    assert response.status_code == 200
    assert "no es correcto" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_a_code_cannot_be_used_twice(client, maria):
    device, _ = enable(maria)
    code = now_code(device)
    password_step(client)
    client.post(VERIFY, {"code": code})
    client.post(reverse("panel:logout"))

    password_step(client)
    response = client.post(VERIFY, {"code": code})

    assert "_auth_user_id" not in client.session
    assert response.status_code == 200


def test_recovery_code_works_once_and_warns(client, maria):
    _, codes = enable(maria)
    mail.outbox.clear()

    password_step(client)
    client.post(VERIFY, {"code": codes[0].upper().replace("-", " ")})
    assert client.session["_auth_user_id"] == str(maria.pk)
    assert any("código de respaldo" in m.subject for m in mail.outbox)
    assert two_factor.remaining_recovery_codes(maria) == 9

    client.post(reverse("panel:logout"))
    password_step(client)
    client.post(VERIFY, {"code": codes[0]})
    assert "_auth_user_id" not in client.session


def test_recovery_codes_are_stored_hashed(maria):
    _, codes = enable(maria)

    stored = set(RecoveryCode.objects.values_list("code_hash", flat=True))
    assert len(codes) == 10 and len(stored) == 10
    assert not any(code in stored or code.replace("-", "") in stored for code in codes)


def test_pending_login_expires(client, maria, settings):
    device, _ = enable(maria)
    password_step(client)
    session = client.session
    session["two_factor_pending"]["at"] -= settings.TWO_FACTOR_PENDING_MINUTES * 60 + 1
    session.save()

    response = client.post(VERIFY, {"code": now_code(device)})

    assert response["Location"] == LOGIN
    assert "_auth_user_id" not in client.session


def test_verify_page_without_password_step_goes_back_to_login(client):
    assert client.get(VERIFY)["Location"] == LOGIN


def test_guessing_codes_is_throttled_and_the_owner_is_warned(client, maria):
    device, _ = enable(maria)
    mail.outbox.clear()
    password_step(client)
    for _ in range(3):
        client.post(VERIFY, {"code": "000000"})

    response = client.post(VERIFY, {"code": now_code(device)})

    assert "demasiados intentos" in response.content.decode()
    assert "_auth_user_id" not in client.session
    warning = next(m for m in mail.outbox if "segundo paso" in m.subject)
    assert warning.to == ["maria@example.com"]


def test_next_url_is_kept_and_external_ones_are_ignored(client, maria):
    device, _ = enable(maria)
    client.post(
        f"{LOGIN}?next=/panel/eventos/",
        {"username": "maria", "password": "clave-correcta-2026"},
    )
    assert client.post(VERIFY, {"code": now_code(device)})["Location"] == "/panel/eventos/"


# --- Activar y administrar ------------------------------------------------------------------------


def test_setup_flow_activates_and_shows_codes_once(client, maria):
    client.force_login(maria)
    page = client.get(SETUP).content.decode()
    device = TwoFactorDevice.objects.get(user=maria)
    assert "otpauth://totp/" in page and "qrcode.js" in page
    assert totp.format_secret(device.secret) in page

    response = client.post(SETUP, {"code": now_code(device)})

    content = response.content.decode()
    assert "Tus códigos de respaldo" in content
    assert "no-store" in response["Cache-Control"]
    assert two_factor.is_enabled(maria)
    assert any("activada" in m.subject for m in mail.outbox)


def test_setup_rejects_a_wrong_code(client, maria):
    client.force_login(maria)
    client.get(SETUP)

    response = client.post(SETUP, {"code": "123456"})

    assert "no coincide" in response.content.decode()
    assert not two_factor.is_enabled(maria)


def test_disable_needs_password_and_code(client, maria):
    device, _ = enable(maria)
    client.force_login(maria)
    url = reverse("panel:two_factor_disable")

    client.post(url, {"password": "mala", "code": now_code(device)})
    assert two_factor.is_enabled(maria)

    client.post(url, {"password": "clave-correcta-2026", "code": now_code(device)})
    assert not two_factor.is_enabled(maria)


def test_regenerate_codes_invalidates_old_ones(client, maria):
    device, old = enable(maria)
    client.force_login(maria)

    response = client.post(
        reverse("panel:two_factor_codes"),
        {"password": "clave-correcta-2026", "code": now_code(device)},
    )

    assert "Tus códigos de respaldo" in response.content.decode()
    assert two_factor.verify(maria, old[1]) is None


def test_admins_must_set_it_up(client, settings):
    settings.TWO_FACTOR_ENFORCE = True
    boss = User.objects.create_user("ana", "ana@example.com", "clave-larga-2026", is_staff=True)
    set_user_roles(boss, [CHURCH_ADMIN.name])
    client.force_login(boss)

    assert client.get(reverse("panel:event_list"))["Location"] == SETUP
    assert client.get(SETUP).status_code == 200
    assert "obligatoria" in client.get(SETUP).content.decode()

    enable(boss)
    assert client.get(reverse("panel:event_list")).status_code == 200


def test_superuser_cannot_skip_it_through_the_admin(client, settings):
    settings.TWO_FACTOR_ENFORCE = True
    boss = User.objects.create_superuser("jefe", "jefe@example.com", "clave-larga-2026")
    client.force_login(boss)

    assert client.get(reverse("admin:index"))["Location"] == SETUP


def test_regular_roles_are_not_forced(client, maria, settings):
    settings.TWO_FACTOR_ENFORCE = True
    client.force_login(maria)

    assert client.get(reverse("panel:dashboard")).status_code == 200


def test_team_admin_can_reset_a_lost_phone(client, maria):
    enable(maria)
    boss = User.objects.create_superuser("jefe", "jefe@example.com", "clave-larga-2026")
    client.force_login(boss)
    mail.outbox.clear()

    edit = client.get(reverse("panel:user_edit", args=[maria.pk])).content.decode()
    assert "Restablecer verificación en dos pasos" in edit
    client.post(reverse("panel:user_two_factor_reset", args=[maria.pk]))

    assert not two_factor.is_enabled(maria)
    assert any(m.to == ["maria@example.com"] and "restablecida" in m.subject for m in mail.outbox)


def test_nobody_resets_their_own_from_the_team_page(client, maria):
    boss = User.objects.create_superuser("jefe", "jefe@example.com", "clave-larga-2026")
    enable(boss)
    client.force_login(boss)

    response = client.post(reverse("panel:user_two_factor_reset", args=[boss.pk]))

    assert response.status_code in (403, 404)
    assert two_factor.is_enabled(boss)


def test_command_resets_from_the_server(maria):
    enable(maria)

    call_command("reset_two_factor", "maria")

    assert not two_factor.is_enabled(maria)


def test_account_page_shows_the_security_center(client, maria):
    client.force_login(maria)

    content = client.get(reverse("panel:account")).content.decode()

    assert "Seguridad de tu cuenta" in content and "Activar verificación" in content
