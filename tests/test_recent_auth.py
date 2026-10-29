"""Acciones delicadas piden la contraseña otra vez."""

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from apps.accounts import totp, two_factor
from apps.accounts.roles import CHURCH_ADMIN, set_user_roles
from apps.contacts.models import ContactMessage

pytestmark = pytest.mark.django_db
User = get_user_model()
CONFIRM = reverse("panel:confirm_identity")
EXPORT = reverse("panel:message_export")


@pytest.fixture(autouse=True)
def enabled(settings, monkeypatch):
    settings.RECENT_AUTH_REQUIRED = True
    settings.RECENT_AUTH_MINUTES = 10
    monkeypatch.setattr("apps.accounts.alerts.transaction.on_commit", lambda func: func())


@pytest.fixture
def ana():
    user = User.objects.create_user("ana", "ana@example.com", "clave-larga-2026", is_staff=True)
    set_user_roles(user, [CHURCH_ADMIN.name])
    return user


def login(client):
    return client.post(reverse("panel:login"), {"username": "ana", "password": "clave-larga-2026"})


def age_session(client, seconds):
    session = client.session
    session["auth_confirmed_at"] -= seconds
    session.save()


def test_right_after_login_no_confirmation_is_needed(client, ana):
    login(client)

    assert client.get(EXPORT).status_code == 200


def test_after_some_minutes_export_asks_again(client, ana):
    login(client)
    age_session(client, 11 * 60)

    response = client.get(EXPORT)

    assert response.status_code == 302
    assert response["Location"].startswith(CONFIRM)


def test_forced_login_without_password_always_asks(client, ana):
    client.force_login(ana)

    assert client.get(reverse("panel:user_create"))["Location"].startswith(CONFIRM)


def test_confirming_lets_you_continue(client, ana):
    client.force_login(ana)

    client.post(CONFIRM, {"password": "mala", "next": EXPORT})
    assert client.get(EXPORT).status_code == 302

    response = client.post(CONFIRM, {"password": "clave-larga-2026", "next": EXPORT})
    assert response["Location"] == EXPORT
    assert client.get(EXPORT).status_code == 200


def test_with_two_factor_a_code_is_also_needed(client, ana):
    device = two_factor.start_setup(ana)
    two_factor.confirm_setup(ana, totp.code_at(device.secret, totp.current_step()))
    device.refresh_from_db()
    device.last_step = 0
    device.save()
    client.force_login(ana)

    client.post(CONFIRM, {"password": "clave-larga-2026", "code": "000000", "next": EXPORT})
    assert client.get(EXPORT).status_code == 302

    client.post(
        CONFIRM,
        {
            "password": "clave-larga-2026",
            "code": totp.code_at(device.secret, totp.current_step()),
            "next": EXPORT,
        },
    )
    assert client.get(EXPORT).status_code == 200


def test_external_next_is_ignored(client, ana):
    client.force_login(ana)

    response = client.post(
        CONFIRM, {"password": "clave-larga-2026", "next": "https://evil.example/"}
    )

    assert response["Location"] == reverse("panel:dashboard")


def test_export_warns_admins_and_is_logged(client, ana):
    from django.contrib.admin.models import LogEntry

    User.objects.create_superuser("jefe", "jefe@example.com", "clave-larga-2026")
    ContactMessage.objects.create(name="A", email="a@b.co", subject="s", message="m")
    login(client)
    mail.outbox.clear()

    client.get(EXPORT)

    message = next(m for m in mail.outbox if "exportaron" in m.subject)
    assert "jefe@example.com" in message.bcc
    assert LogEntry.objects.filter(change_message__startswith="Exportar 1 ").exists()


def test_guessing_the_password_here_is_throttled(client, ana, settings):
    settings.LOGIN_RATE_LIMIT = (3, 50, 900)
    client.force_login(ana)
    for _ in range(3):
        client.post(CONFIRM, {"password": "mala", "next": EXPORT})

    response = client.post(CONFIRM, {"password": "clave-larga-2026", "next": EXPORT})

    assert "demasiados intentos" in response.content.decode()
