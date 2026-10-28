"""Ingreso sin sorpresas: intentos restantes, desbloqueo y contraseñas que piden cambio."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from apps.accounts import totp, two_factor
from apps.accounts.models import LoginAttempt

pytestmark = pytest.mark.django_db
User = get_user_model()
LOGIN = reverse("panel:login")


@pytest.fixture(autouse=True)
def limits(settings, monkeypatch):
    settings.LOGIN_RATE_LIMIT = (5, 20, 900)
    monkeypatch.setattr("apps.accounts.alerts.transaction.on_commit", lambda func: func())


def make(password="clave-correcta-2026"):
    return User.objects.create_user("maria", "maria@example.com", password, is_staff=True)


def attempt(client, password):
    return client.post(
        LOGIN, {"username": "maria", "password": password}, REMOTE_ADDR="203.0.113.5"
    )


def test_warns_before_locking(client):
    make()
    for _ in range(2):
        content = attempt(client, "mala").content.decode()
        assert "Te quedan" not in content

    assert "Te quedan 2 intentos" in attempt(client, "mala").content.decode()
    assert "Te queda 1 intento " in attempt(client, "mala").content.decode()
    assert "demasiados intentos" not in attempt(client, "mala").content.decode()  # el 5.º
    assert "demasiados intentos" in attempt(client, "clave-correcta-2026").content.decode()


def test_recovering_the_password_unlocks_the_account(client):
    make()
    for _ in range(5):
        attempt(client, "mala")
    assert LoginAttempt.objects.exists()

    client.post(reverse("panel:password_reset"), {"email": "maria@example.com"})
    reset = next(m for m in mail.outbox if "Restablece" in m.subject)
    link = re.search(r"https?://[^/\s]+(/panel/recuperar/\S+/)", reset.body).group(1)
    form_url = client.get(link, follow=True).redirect_chain[-1][0]
    new = "otra-clave-segura-26"
    client.post(form_url, {"new_password1": new, "new_password2": new})

    assert any("Tu contraseña cambió" in m.subject for m in mail.outbox)
    response = attempt(client, new)
    assert response.status_code == 302 and response["Location"] == reverse("panel:dashboard")


def test_weak_password_is_accepted_but_must_be_changed(client):
    make(password="corta12")  # anterior a la regla de 10 caracteres

    response = attempt(client, "corta12")
    assert response.status_code == 302
    page = client.get(reverse("panel:account"))
    assert page["Location"] == reverse("panel:password_change")
    assert client.get(reverse("panel:password_change")).status_code == 200

    new = "una-clave-nueva-larga"
    client.post(
        reverse("panel:password_change"),
        {"old_password": "corta12", "new_password1": new, "new_password2": new},
    )
    assert client.get(reverse("panel:account")).status_code == 200


def test_strong_password_goes_straight_in(client):
    make()
    attempt(client, "clave-correcta-2026")

    assert client.get(reverse("panel:account")).status_code == 200


def test_weak_password_with_two_factor_is_also_upgraded(client):
    user = make(password="corta12")
    device = two_factor.start_setup(user)
    two_factor.confirm_setup(user, totp.code_at(device.secret, totp.current_step()))
    device.refresh_from_db()
    device.last_step = 0
    device.save()

    attempt(client, "corta12")
    client.post(
        reverse("panel:two_factor_verify"),
        {"code": totp.code_at(device.secret, totp.current_step())},
    )

    assert client.get(reverse("panel:account"))["Location"] == reverse("panel:password_change")
