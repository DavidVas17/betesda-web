"""Correos con diseño: HTML y texto con el mismo contenido."""

import pytest
from django.core import mail
from django.urls import reverse

from apps.core.emails import Email

pytestmark = pytest.mark.django_db


def sample(**extra):
    return Email(
        subject="Asunto",
        title="Título del aviso",
        paragraphs=["Primer párrafo.", "Segundo párrafo."],
        details=[("Dispositivo", "Chrome en Windows"), ("IP", "203.0.113.5")],
        button=("Abrir en el panel", "https://iglesia.example/panel/"),
        note="Nota importante.",
        **extra,
    )


def test_text_and_html_carry_the_same_content():
    email = sample()
    text, html = email.text(), email.html()

    for piece in (
        "Título del aviso",
        "Primer párrafo.",
        "Chrome en Windows",
        "https://iglesia.example/panel/",
        "Nota importante.",
    ):
        assert piece in text
        assert piece in html


def test_message_has_html_alternative():
    message = sample().message(to=["a@example.com"])

    assert message.body.startswith("Título del aviso")
    html, mimetype = message.alternatives[0]
    assert mimetype == "text/html"
    assert "<table" in html and "Betesda" in html


def test_values_are_escaped_in_html():
    html = Email(subject="x", title="x", details=[("Usuario", "<script>alert(1)</script>")]).html()

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_alert_tone_shows_the_security_band():
    assert "Aviso de seguridad" in sample(tone="alert").html()
    assert "Aviso de seguridad" not in sample().html()


def test_password_reset_mail_is_branded(client, django_user_model):
    django_user_model.objects.create_user(
        "maria", "maria@example.com", "clave-larga-2026", is_staff=True
    )

    client.post(reverse("panel:password_reset"), {"email": "maria@example.com"})

    message = mail.outbox[0]
    html = message.alternatives[0][0]
    assert "Elegir contraseña nueva" in html
    assert "/panel/recuperar/" in html and "/panel/recuperar/" in message.body
