"""Freno a los intentos de adivinar contraseñas."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import LoginAttempt
from apps.accounts.throttle import purge_old_attempts

pytestmark = pytest.mark.django_db
User = get_user_model()
LOGIN = reverse("panel:login")


@pytest.fixture(autouse=True)
def limits(settings):
    settings.LOGIN_RATE_LIMIT = (3, 6, 900)


@pytest.fixture
def staff():
    return User.objects.create_user(username="maria", password="clave-correcta-2026", is_staff=True)


def attempt(client, password, username="maria", ip="203.0.113.5"):
    return client.post(LOGIN, {"username": username, "password": password}, REMOTE_ADDR=ip)


def test_blocks_after_repeated_failures_even_with_the_right_password(client, staff):
    for _ in range(3):
        attempt(client, "equivocada")

    response = attempt(client, "clave-correcta-2026")

    assert response.status_code == 200
    assert "demasiados intentos" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_username_is_matched_without_case(client, staff):
    for name in ("maria", "MARIA", " Maria "):
        attempt(client, "equivocada", username=name)

    assert "demasiados intentos" in attempt(client, "clave-correcta-2026").content.decode()


def test_other_connections_can_still_sign_in(client, staff):
    for _ in range(3):
        attempt(client, "equivocada", ip="198.51.100.7")

    response = attempt(client, "clave-correcta-2026", ip="203.0.113.5")

    assert response.status_code == 302


def test_success_clears_previous_failures(client, staff):
    attempt(client, "equivocada")
    attempt(client, "equivocada")
    attempt(client, "clave-correcta-2026")

    assert not LoginAttempt.objects.exists()


def test_ip_limit_stops_trying_many_usernames(client, staff):
    for index in range(6):
        attempt(client, "x", username=f"persona{index}")

    assert "demasiados intentos" in attempt(client, "clave-correcta-2026").content.decode()


def test_failures_outside_the_window_do_not_count(client, staff):
    for _ in range(3):
        attempt(client, "equivocada")
    LoginAttempt.objects.update(created_at=timezone.now() - timedelta(seconds=901))

    assert attempt(client, "clave-correcta-2026").status_code == 302


def test_admin_login_goes_through_the_protected_panel_login(client):
    """El admin no tiene formulario propio: se ingresa por el panel (freno y 2FA)."""
    response = client.get(reverse("admin:login"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("panel:login"))
    assert client.post(reverse("admin:login"), {"username": "x"}).status_code == 302


def test_purge_keeps_recent_attempts():
    old = LoginAttempt.objects.create(username="a", ip_address="203.0.113.5")
    LoginAttempt.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=2))
    LoginAttempt.objects.create(username="b", ip_address="203.0.113.5")

    assert purge_old_attempts() == 1
    assert list(LoginAttempt.objects.values_list("username", flat=True)) == ["b"]
