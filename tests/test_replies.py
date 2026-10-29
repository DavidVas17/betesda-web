"""Respuestas listas para atender peticiones y mensajes."""

from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.contacts import replies
from apps.contacts.models import ContactMessage

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def pastor():
    return User.objects.create_user("pastor", first_name="Luis", last_name="Gómez")


def prayer(**extra):
    values = {
        "name": "Ana María Pérez",
        "email": "ana@example.com",
        "subject": "Salud de mi mamá",
        "message": "…",
        "kind": ContactMessage.Kind.PRAYER,
        "phone": "4171-3008",
    }
    values.update(extra)
    return ContactMessage.objects.create(**values)


def body_of(url):
    return parse_qs(urlsplit(url).query)["body" if url.startswith("mailto:") else "text"][0]


def test_prayer_replies_are_personal_and_signed(pastor):
    options = replies.options(prayer(), pastor, "https://iglesia.example/contacto/")

    labels = [option["label"] for option in options]
    assert labels[0] == "Estamos orando por ti"
    assert "Gracias por escribir" not in labels
    body = body_of(options[0]["email_url"])
    assert body.startswith("Hola Ana:")
    assert "Luis Gómez" in body


def test_contact_messages_get_their_own_replies(pastor):
    options = replies.options(
        prayer(kind=ContactMessage.Kind.CONTACT), pastor, "https://iglesia.example/"
    )

    labels = [option["label"] for option in options]
    assert "Gracias por escribir" in labels and "Estamos orando por ti" not in labels
    assert "«Salud de mi mamá»" in body_of(options[0]["email_url"])


def test_mailto_uses_percent_encoding_not_plus_signs():
    url = replies.mailto(prayer())

    assert "+" not in url.split("?", 1)[1]
    assert unquote(url).endswith("subject=Re: Salud de mi mamá")


def test_whatsapp_uses_the_guatemalan_country_code(pastor):
    options = replies.options(prayer(), pastor, "https://iglesia.example/")

    assert options[0]["whatsapp_url"].startswith("https://wa.me/50241713008?text=")
    assert replies.whatsapp_number("") == ""
    assert replies.whatsapp_number("123") == ""


def test_detail_page_lists_ready_replies(admin_client):
    item = prayer()

    content = admin_client.get(reverse("panel:message_detail", args=[item.pk])).content.decode()

    assert "Respuestas listas" in content
    assert "https://wa.me/50241713008" in content
