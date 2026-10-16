"""Recuperar la contraseña del panel por correo."""

import re

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

pytestmark = pytest.mark.django_db
User = get_user_model()
RESET = reverse("panel:password_reset")


@pytest.fixture
def maria():
    return User.objects.create_user(
        username="maria", email="maria@example.com", password="vieja-clave-2026", is_staff=True
    )


def reset_link():
    return re.search(r"https?://[^/]+(/panel/recuperar/\S+/)", mail.outbox[-1].body).group(1)


def test_login_page_offers_password_recovery(client):
    assert RESET in client.get(reverse("panel:login")).content.decode()


def test_full_reset_flow(client, maria):
    response = client.post(RESET, {"email": "MARIA@example.com"})

    assert response.status_code == 302
    assert response["Location"] == reverse("panel:password_reset_done")
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["maria@example.com"]
    assert "maria" in message.body and "2 horas" in message.body

    form_url = client.get(reset_link(), follow=True).redirect_chain[-1][0]
    response = client.post(
        form_url,
        {"new_password1": "nueva-clave-segura-26", "new_password2": "nueva-clave-segura-26"},
        follow=True,
    )

    maria.refresh_from_db()
    assert maria.check_password("nueva-clave-segura-26")
    assert "Tu contraseña cambió" in response.content.decode()
    assert LogEntry.objects.filter(user=maria, change_message__icontains="Restablecer").exists()


def test_link_works_only_once(client, maria):
    client.post(RESET, {"email": "maria@example.com"})
    link = reset_link()
    form_url = client.get(link, follow=True).redirect_chain[-1][0]
    data = {"new_password1": "nueva-clave-segura-26", "new_password2": "nueva-clave-segura-26"}
    client.post(form_url, data)

    content = client.get(link, follow=True).content.decode()

    assert "Este enlace ya no es válido" in content


def test_unknown_or_non_team_emails_get_the_same_answer_without_mail(client):
    User.objects.create_user(username="visita", email="visita@example.com", password="x")

    for email in ("nadie@example.com", "visita@example.com"):
        response = client.post(RESET, {"email": email})
        assert response.status_code == 302
    assert mail.outbox == []


def test_inactive_accounts_cannot_reset(client, maria):
    maria.is_active = False
    maria.save()

    client.post(RESET, {"email": "maria@example.com"})

    assert mail.outbox == []


def test_requests_are_rate_limited(client, maria, settings):
    settings.LOGIN_RATE_LIMIT = (2, 10, 900)
    client.post(RESET, {"email": "maria@example.com"})
    client.post(RESET, {"email": "maria@example.com"})

    response = client.post(RESET, {"email": "maria@example.com"})

    assert response.status_code == 200
    assert "demasiados intentos" in response.content.decode()
    assert len(mail.outbox) == 2
