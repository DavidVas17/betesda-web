"""Aviso por correo al equipo cuando entra una petición o un mensaje."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.roles import CARE, CHURCH_ADMIN, GALLERY, set_user_roles
from apps.contacts.models import ContactMessage

pytestmark = pytest.mark.django_db
User = get_user_model()

PRIVATE_TEXT = "Por favor oren por la salud de mi mamá"


def member(username, role, email=None, **extra):
    user = User.objects.create_user(
        username=username, email=email or f"{username}@example.com", is_staff=True, **extra
    )
    set_user_roles(user, [role.name])
    return user


def send(client, **extra):
    data = {
        "kind": "PRAYER",
        "name": "Ana Pérez",
        "email": "ana@example.com",
        "subject": "Salud de mi familia",
        "message": PRIVATE_TEXT,
        "privacy_accepted": "on",
    }
    data.update(extra)
    return client.post(reverse("contacts:send"), data)


def test_team_that_reads_messages_gets_a_private_notice(
    client, mailoutbox, django_capture_on_commit_callbacks
):
    member("oracion", CARE)
    member("pastor", CHURCH_ADMIN)
    member("fotos", GALLERY)  # no lee mensajes
    member("silencio", CARE, notify_new_messages=False)
    member("inactiva", CARE, is_active=False)

    with django_capture_on_commit_callbacks(execute=True):
        send(client)

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.subject == "[Betesda] Nueva petición de oración"
    assert sorted(email.bcc) == ["oracion@example.com", "pastor@example.com"]
    assert email.to == []
    message = ContactMessage.objects.get()
    assert reverse("panel:message_detail", args=[message.pk]) in email.body
    # El contenido y los datos de la persona nunca viajan por correo.
    for private in (PRIVATE_TEXT, "Ana Pérez", "ana@example.com", "Salud de mi familia"):
        assert private not in email.body
        assert private not in email.subject


def test_contact_messages_use_their_own_subject(
    client, mailoutbox, django_capture_on_commit_callbacks
):
    member("pastor", CHURCH_ADMIN)

    with django_capture_on_commit_callbacks(execute=True):
        send(client, kind="CONTACT")

    assert mailoutbox[0].subject == "[Betesda] Nuevo mensaje de contacto"


def test_no_recipients_means_no_email(client, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        send(client)

    assert mailoutbox == []
    assert ContactMessage.objects.count() == 1


def test_a_failing_mail_server_does_not_lose_the_request(
    client, settings, django_capture_on_commit_callbacks
):
    member("pastor", CHURCH_ADMIN)
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "127.0.0.1"
    settings.EMAIL_PORT = 9  # nada escucha aquí
    settings.EMAIL_TIMEOUT = 1

    with django_capture_on_commit_callbacks(execute=True):
        response = send(client)

    assert response.status_code == 302
    assert ContactMessage.objects.count() == 1


def test_people_who_read_messages_can_turn_the_notice_off(client):
    user = member("oracion", CARE)
    client.force_login(user)

    page = client.get(reverse("panel:account")).content.decode()
    client.post(
        reverse("panel:account"),
        {"first_name": "Rut", "last_name": "", "email": "oracion@example.com"},
    )

    assert "Avisarme por correo de mensajes nuevos" in page
    user.refresh_from_db()
    assert user.notify_new_messages is False
    assert user.first_name == "Rut"


def test_the_option_is_hidden_for_roles_that_do_not_read_messages(client):
    client.force_login(member("fotos", GALLERY))

    assert "Avisarme por correo" not in client.get(reverse("panel:account")).content.decode()


def test_church_inbox_always_gets_the_notice(
    client, settings, mailoutbox, django_capture_on_commit_callbacks
):
    settings.CONTACT_NOTIFY_EMAILS = ["iglesia@example.com", " "]
    member("pastor", CHURCH_ADMIN)

    with django_capture_on_commit_callbacks(execute=True):
        send(client)

    assert sorted(mailoutbox[0].bcc) == ["iglesia@example.com", "pastor@example.com"]
    assert PRIVATE_TEXT not in mailoutbox[0].body


def test_church_inbox_works_even_without_team_accounts(
    client, settings, mailoutbox, django_capture_on_commit_callbacks
):
    settings.CONTACT_NOTIFY_EMAILS = ["iglesia@example.com"]

    with django_capture_on_commit_callbacks(execute=True):
        send(client)

    assert mailoutbox[0].bcc == ["iglesia@example.com"]
