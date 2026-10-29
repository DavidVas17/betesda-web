"""Responder peticiones y mensajes desde el panel con el correo de la iglesia."""

from unittest import mock
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from apps.accounts.roles import CARE, READ_ONLY, set_user_roles
from apps.contacts import replies
from apps.contacts.models import ContactMessage, MessageReply

pytestmark = pytest.mark.django_db
User = get_user_model()
SITE = {"url": "https://iglesia.example/", "phone": "4171-3008"}


@pytest.fixture
def pastor():
    user = User.objects.create_user(
        "pastor", first_name="Luis", last_name="Gómez", password="clave-larga-2026", is_staff=True
    )
    set_user_roles(user, [CARE.name])
    return user


def prayer(**extra):
    values = {
        "name": "Ana María Pérez",
        "email": "ana@example.com",
        "subject": "Salud de mi mamá",
        "message": "Oren por mi mamá",
        "kind": ContactMessage.Kind.PRAYER,
        "phone": "4171-3008",
    }
    values.update(extra)
    return ContactMessage.objects.create(**values)


def detail(item):
    return reverse("panel:message_detail", args=[item.pk])


# --- Textos -------------------------------------------------------------------------------------


def test_prayer_templates_are_personal_and_signed(pastor):
    item = prayer()

    keys = [reply.key for reply in replies.available(item)]
    assert keys == ["oracion", "acompanar", "visita", "detalles"]
    body = replies.render(replies.REPLIES_BY_KEY["oracion"], item, pastor, SITE)
    assert body.startswith("Hola Ana:")
    assert "Luis Gómez" in body and "Salmo 55:22" in body


def test_contact_templates_mention_subject_and_phone(pastor):
    item = prayer(kind=ContactMessage.Kind.CONTACT)

    keys = [reply.key for reply in replies.available(item)]
    assert "gracias" in keys and "oracion" not in keys
    body = replies.render(replies.REPLIES_BY_KEY["gracias"], item, pastor, SITE)
    assert "«Salud de mi mamá»" in body and "4171-3008" in body


def test_whatsapp_and_mailto_links(pastor):
    item = prayer()

    option = replies.options(item, pastor, SITE)[0]
    assert option["whatsapp_url"].startswith("https://wa.me/50241713008?text=Hola%20Ana")
    url = replies.mailto(item)
    assert "+" not in url.split("?", 1)[1]
    assert unquote(url).endswith("subject=Re: Salud de mi mamá")


# --- Enviar desde el panel ----------------------------------------------------------------------


def test_choosing_a_template_fills_the_form(client, pastor):
    item = prayer()
    client.force_login(pastor)

    content = client.get(detail(item) + "?plantilla=oracion").content.decode()

    assert "Hola Ana:" in content
    assert "Re: Salud de mi mamá" in content
    assert "Estamos orando por ti" in content and "Queremos acompañarte" in content


def test_sending_uses_the_church_email_and_keeps_history(client, pastor, settings):
    settings.DEFAULT_FROM_EMAIL = "Betesda Rosa de Sarón <iglesia@example.com>"
    settings.CONTACT_NOTIFY_EMAILS = ["iglesia@example.com"]
    item = prayer()
    client.force_login(pastor)

    response = client.post(
        reverse("panel:message_reply", args=[item.pk]),
        {"subject": "Re: Salud de mi mamá", "body": "Hola Ana:\n\nEstamos orando.\n\nLuis"},
    )

    assert response.status_code == 302
    message = mail.outbox[0]
    assert message.to == ["ana@example.com"]
    assert message.from_email == "Betesda Rosa de Sarón <iglesia@example.com>"
    assert message.reply_to == ["iglesia@example.com"]
    html = message.alternatives[0][0]
    assert "Sobre tu petición de oración" in html and "Estamos orando." in html
    saved = MessageReply.objects.get()
    assert saved.author == pastor and saved.body.startswith("Hola Ana:")
    item.refresh_from_db()
    assert item.status == ContactMessage.Status.IN_PROGRESS
    assert item.assigned_to == pastor
    assert LogEntry.objects.filter(change_message="Respuesta enviada por correo.").exists()
    assert "Respuestas enviadas" in client.get(detail(item)).content.decode()


def test_a_mail_failure_saves_nothing_and_says_so(client, pastor):
    item = prayer()
    client.force_login(pastor)

    with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError):
        response = client.post(
            reverse("panel:message_reply", args=[item.pk]),
            {"subject": "Re: x", "body": "Hola"},
            follow=True,
        )

    assert "No se pudo enviar el correo" in response.content.decode()
    assert not MessageReply.objects.exists()
    item.refresh_from_db()
    assert item.status == ContactMessage.Status.NEW


def test_empty_reply_is_not_sent(client, pastor):
    item = prayer()
    client.force_login(pastor)

    client.post(reverse("panel:message_reply", args=[item.pk]), {"subject": "", "body": ""})

    assert mail.outbox == [] and not MessageReply.objects.exists()


def test_read_only_people_cannot_reply(client):
    viewer = User.objects.create_user("lector", is_staff=True)
    set_user_roles(viewer, [READ_ONLY.name])
    item = prayer()
    client.force_login(viewer)

    response = client.post(
        reverse("panel:message_reply", args=[item.pk]), {"subject": "x", "body": "y"}
    )

    assert response.status_code == 403
    assert mail.outbox == []


def test_replies_are_deleted_with_their_request(pastor):
    item = prayer()
    MessageReply.objects.create(message=item, author=pastor, subject="s", body="b")

    item.delete()

    assert not MessageReply.objects.exists()


def test_sent_body_is_escaped_in_the_email(client, pastor):
    item = prayer()
    client.force_login(pastor)

    client.post(
        reverse("panel:message_reply", args=[item.pk]),
        {"subject": "Re: x", "body": "<script>alert(1)</script>"},
    )

    assert "<script>alert(1)</script>" not in mail.outbox[0].alternatives[0][0]


def test_template_key_for_another_kind_is_ignored(client, pastor):
    item = prayer()
    client.force_login(pastor)

    content = client.get(detail(item) + "?plantilla=gracias").content.decode()

    assert "Gracias por escribirnos" not in content
    assert parse_qs(urlsplit(replies.mailto(item)).query)["subject"] == ["Re: Salud de mi mamá"]
