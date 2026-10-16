"""Avisos de seguridad por correo."""

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from apps.accounts.alerts import DEVICE_COOKIE, device_label
from apps.accounts.models import KnownDevice
from apps.accounts.roles import CARE, CHURCH_ADMIN, set_user_roles

pytestmark = pytest.mark.django_db
User = get_user_model()
LOGIN = reverse("panel:login")
CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/141.0 Safari/537.36"
)


@pytest.fixture(autouse=True)
def config(settings):
    settings.LOGIN_RATE_LIMIT = (3, 6, 900)
    settings.SECURITY_ALERT_EMAILS = ["seguridad@example.com"]


@pytest.fixture(autouse=True)
def deliver_now(monkeypatch):
    """En las pruebas todo corre dentro de una transacción: el aviso se envía al momento."""
    monkeypatch.setattr("apps.accounts.alerts.transaction.on_commit", lambda func: func())


@pytest.fixture
def boss():
    user = User.objects.create_superuser("jefe", "jefe@example.com", "clave-larga-2026")
    mail.outbox.clear()  # crear un superusuario también avisa; aquí no interesa
    return user


@pytest.fixture
def maria():
    return User.objects.create_user(
        "maria", "maria@example.com", "clave-correcta-2026", is_staff=True
    )


def login(client, password="clave-correcta-2026", username="maria", ip="203.0.113.5"):
    return client.post(
        LOGIN,
        {"username": username, "password": password},
        REMOTE_ADDR=ip,
        HTTP_USER_AGENT=CHROME_WINDOWS,
    )


def subjects():
    return [message.subject for message in mail.outbox]


def recipients_of(subject_part):
    message = next(m for m in mail.outbox if subject_part in m.subject)
    return set(message.to) | set(message.bcc)


def test_device_labels_are_readable():
    assert device_label(CHROME_WINDOWS) == "Chrome en Windows"
    assert device_label("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0) Safari/604.1") == (
        "Safari en iPhone/iPad"
    )
    assert device_label("") == "Navegador"


def test_lockout_warns_the_owner_and_admins_once(client, boss, maria):
    for _ in range(5):
        login(client, "equivocada")

    assert (
        subjects().count("[Betesda · Seguridad] Varios intentos fallidos de ingreso en tu cuenta")
        == 1
    )
    assert recipients_of("Varios intentos") == {
        "maria@example.com",
        "jefe@example.com",
        "seguridad@example.com",
    }
    assert "equivocada" not in mail.outbox[0].body


def test_trying_many_usernames_warns_admins(client, boss):
    for index in range(6):
        login(client, "x", username=f"persona{index}")

    assert recipients_of("muchos intentos desde una conexión") == {
        "jefe@example.com",
        "seguridad@example.com",
    }


def test_first_login_is_silent_and_new_device_warns(client, maria):
    login(client)
    assert mail.outbox == []
    assert KnownDevice.objects.filter(user=maria).count() == 1
    assert DEVICE_COOKIE in client.cookies

    client.post(reverse("panel:logout"))
    login(client)  # mismo navegador: la cookie lo reconoce
    assert mail.outbox == []

    other = client.__class__()
    login(other, ip="198.51.100.20")
    assert subjects() == ["[Betesda · Seguridad] Nuevo inicio de sesión en tu cuenta"]
    body = mail.outbox[0].body
    assert "Chrome en Windows" in body and "198.51.100.20" in body
    assert mail.outbox[0].to == ["maria@example.com"]


def test_device_cookie_is_httponly_and_only_a_hash_is_stored(client, maria):
    login(client)

    cookie = client.cookies[DEVICE_COOKIE]
    assert cookie["httponly"]
    assert not KnownDevice.objects.filter(key=cookie.value).exists()


def test_granting_church_admin_warns(boss, maria):
    set_user_roles(maria, [CHURCH_ADMIN.name])

    assert recipients_of("privilegios de administración") == {
        "maria@example.com",
        "jefe@example.com",
        "seguridad@example.com",
    }


def test_ordinary_roles_do_not_warn(maria):
    set_user_roles(maria, [CARE.name])

    assert mail.outbox == []


def test_becoming_superuser_warns(boss, maria):
    maria.is_superuser = True
    maria.save()
    maria.save()  # guardar de nuevo no repite el aviso

    assert subjects().count("[Betesda · Seguridad] Se otorgaron privilegios de administración") == 1


def test_new_team_account_warns_other_admins(client, boss):
    admin = User.objects.create_user("ana", "ana@example.com", "clave-larga-2026", is_staff=True)
    set_user_roles(admin, [CHURCH_ADMIN.name])
    mail.outbox.clear()
    client.force_login(admin)

    client.post(
        reverse("panel:user_create"),
        {
            "username": "nuevo",
            "email": "nuevo@example.com",
            "password1": "una-clave-muy-larga-26",
            "password2": "una-clave-muy-larga-26",
            "roles": [CARE.name],
            "is_active": "on",
        },
    )

    assert User.objects.filter(username="nuevo").exists()
    assert recipients_of("Se creó una cuenta") == {"jefe@example.com", "seguridad@example.com"}


def test_password_change_by_another_person_warns_the_owner(client, boss, maria):
    client.force_login(boss)

    client.post(
        reverse("panel:user_password", args=[maria.pk]),
        {"new_password1": "otra-clave-larga-26", "new_password2": "otra-clave-larga-26"},
    )

    message = next(m for m in mail.outbox if "Tu contraseña cambió" in m.subject)
    assert message.to == ["maria@example.com"]
    assert "jefe" in message.body


def test_devices_unused_for_a_year_are_forgotten(maria):
    from datetime import timedelta

    from django.utils import timezone

    from apps.accounts.throttle import purge_stale_devices

    old = KnownDevice.objects.create(user=maria, key="a" * 64, label="Viejo")
    KnownDevice.objects.filter(pk=old.pk).update(last_seen=timezone.now() - timedelta(days=400))
    KnownDevice.objects.create(user=maria, key="b" * 64, label="Actual")

    assert purge_stale_devices() == 1
    assert list(KnownDevice.objects.values_list("label", flat=True)) == ["Actual"]
