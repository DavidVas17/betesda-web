"""Límite de envíos del formulario público e IP real detrás del proxy."""

import itertools
from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.contacts.models import ContactMessage
from apps.contacts.protection import client_ip

pytestmark = pytest.mark.django_db


_sequence = itertools.count()


def contact_data(**extra):
    # Cada envío es de una persona distinta: aquí se prueba el límite por IP, no el de correo
    # ni el de mensajes duplicados.
    number = next(_sequence)
    data = {
        "kind": "PRAYER",
        "name": "María",
        "email": f"persona{number}@example.com",
        "subject": "Oración por mi familia",
        "message": f"Gracias por orar ({number}).",
        "privacy_accepted": "on",
    }
    data.update(extra)
    return data


def test_sixth_message_in_ten_minutes_from_same_ip_is_held(client, settings):
    settings.CONTACT_RATE_LIMIT = (5, 600)
    for _ in range(5):
        client.post(reverse("contacts:send"), contact_data())

    response = client.post(reverse("contacts:send"), contact_data(subject="Sexto"))

    assert response.status_code == 429
    assert "Espera unos minutos" in response.content.decode()
    assert ContactMessage.objects.count() == 5
    assert "Sexto" in response.content.decode()  # lo escrito no se pierde


def test_old_messages_do_not_count_toward_the_limit(client, settings):
    settings.CONTACT_RATE_LIMIT = (2, 600)
    for _ in range(2):
        client.post(reverse("contacts:send"), contact_data())
    ContactMessage.objects.update(created_at=timezone.now() - timedelta(minutes=11))

    response = client.post(reverse("contacts:send"), contact_data())

    assert response.status_code == 302
    assert ContactMessage.objects.count() == 3


def test_limit_is_per_visitor(client, settings):
    settings.CONTACT_RATE_LIMIT = (1, 600)
    client.post(reverse("contacts:send"), contact_data(), REMOTE_ADDR="192.0.2.1")

    response = client.post(reverse("contacts:send"), contact_data(), REMOTE_ADDR="192.0.2.2")

    assert response.status_code == 302


def test_client_ip_ignores_forwarded_header_unless_proxy_is_trusted(settings):
    request = RequestFactory().post(
        "/", REMOTE_ADDR="172.18.0.3", HTTP_X_FORWARDED_FOR="203.0.113.9"
    )
    settings.TRUST_X_FORWARDED_FOR = False
    assert client_ip(request) == "172.18.0.3"

    settings.TRUST_X_FORWARDED_FOR = True
    assert client_ip(request) == "203.0.113.9"


def test_client_ip_uses_the_hop_added_by_our_proxy(settings):
    settings.TRUST_X_FORWARDED_FOR = True
    request = RequestFactory().post(
        "/", REMOTE_ADDR="172.18.0.3", HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.9"
    )

    # Un visitante puede inventar la primera IP; la última la escribe Caddy.
    assert client_ip(request) == "203.0.113.9"


def test_invalid_ip_values_are_discarded(settings):
    settings.TRUST_X_FORWARDED_FOR = True
    request = RequestFactory().post("/", HTTP_X_FORWARDED_FOR="no-es-una-ip")

    assert client_ip(request) is None
