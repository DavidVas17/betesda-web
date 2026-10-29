"""Ingresos y fallos visibles en la bitácora."""

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.roles import CARE, CHURCH_ADMIN, set_user_roles

pytestmark = pytest.mark.django_db
User = get_user_model()
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0 Safari/537.36"


def test_sign_in_and_out_are_logged_with_device_and_ip(client):
    User.objects.create_user("ana", "ana@example.com", "clave-larga-2026", is_staff=True)

    client.post(
        reverse("panel:login"),
        {"username": "ana", "password": "clave-larga-2026"},
        REMOTE_ADDR="203.0.113.5",
        HTTP_USER_AGENT=CHROME,
    )
    client.post(reverse("panel:logout"), REMOTE_ADDR="203.0.113.5")

    messages = list(LogEntry.objects.order_by("pk").values_list("change_message", flat=True))
    assert messages == [
        "Inicio de sesión · Chrome en Windows · IP 203.0.113.5",
        "Cierre de sesión · Navegador · IP 203.0.113.5",
    ]


def test_activity_shows_recent_failed_attempts(client):
    boss = User.objects.create_user("jefa", "j@example.com", "clave-larga-2026", is_staff=True)
    set_user_roles(boss, [CHURCH_ADMIN.name])
    for _ in range(2):
        client.post(
            reverse("panel:login"),
            {"username": "pedro", "password": "x"},
            REMOTE_ADDR="198.51.100.7",
        )
    client.force_login(boss)

    content = client.get(reverse("panel:activity")).content.decode()

    assert "Intentos fallidos de ingreso" in content
    assert "pedro" in content and "198.51.100.7" in content


def test_only_people_with_activity_permission_see_it(client):
    user = User.objects.create_user("ana", "ana@example.com", "clave-larga-2026", is_staff=True)
    set_user_roles(user, [CARE.name])
    client.force_login(user)

    assert client.get(reverse("panel:activity")).status_code == 403
