import csv
import io

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from apps.contacts.models import ContactMessage

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def incoming_message():
    return ContactMessage.objects.create(
        name="María López",
        email="maria@example.com",
        phone="+502 4171-3008",
        subject="Oración por nuestra familia",
        message="Una petición privada que solo debe leer el equipo.",
        kind=ContactMessage.Kind.PRAYER,
        privacy_accepted=True,
        source_ip="192.0.2.10",
    )


@pytest.fixture
def message_viewer():
    user = User.objects.create_user(username="solo-lectura", is_staff=True)
    user.groups.clear()
    user.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="contacts", codename="view_contactmessage"
        )
    )
    return user


def csv_rows(response):
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert response.content.startswith(b"\xef\xbb\xbf")
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


@pytest.mark.parametrize("kind", [ContactMessage.Kind.PRAYER, ContactMessage.Kind.CONTACT])
def test_public_submission_is_received_in_new_panel_and_uses_existing_database(
    client, admin_client, admin_user, kind
):
    response = client.post(
        reverse("contacts:send"),
        {
            "kind": kind,
            "name": "Lucía Pérez",
            "email": "lucia@example.com",
            "phone": "4171-3008",
            "subject": "Solicitud enviada desde el sitio",
            "message": "Queremos recibir acompañamiento.",
            "privacy_accepted": "on",
            "website": "",
        },
        REMOTE_ADDR="192.0.2.12",
    )
    assert response.status_code == 302
    message = ContactMessage.objects.get()

    response = admin_client.get(reverse("panel:message_list"), {"status": "NEW"})
    assert response.status_code == 200
    assert message.subject in response.content.decode()
    assert message.get_kind_display() in response.content.decode()

    response = admin_client.get(reverse("panel:message_detail", args=[message.pk]))
    assert response.status_code == 200
    assert message.message in response.content.decode()
    assert message.email in response.content.decode()
    assert message.phone in response.content.decode()

    response = admin_client.post(
        reverse("panel:message_action", args=[message.pk]), {"action": "close"}
    )
    assert response.status_code == 302
    message.refresh_from_db()
    assert message.status == ContactMessage.Status.CLOSED
    assert message.assigned_to == admin_user
    assert message.source_ip == "192.0.2.12"

    response = admin_client.get(reverse("admin:contacts_contactmessage_change", args=[message.pk]))
    assert response.context["original"].pk == message.pk
    assert response.context["original"].status == ContactMessage.Status.CLOSED
    assert admin_client.get(reverse("panel:dashboard")).context["panel_new_messages"] == 0


def test_reader_can_review_messages_but_cannot_mutate_them(
    client, message_viewer, incoming_message
):
    client.force_login(message_viewer)
    detail = reverse("panel:message_detail", args=[incoming_message.pk])
    action = reverse("panel:message_action", args=[incoming_message.pk])

    assert client.get(reverse("panel:message_list")).status_code == 200
    assert client.get(detail).status_code == 200
    # Ver una petición de oración no autoriza a sacar todas en un archivo.
    assert client.get(reverse("panel:message_export")).status_code == 403
    assert (
        client.post(detail, {"status": "CLOSED", "internal_notes": "Manipulada"}).status_code == 403
    )
    assert client.post(action, {"action": "close"}).status_code == 403
    incoming_message.refresh_from_db()
    assert incoming_message.status == ContactMessage.Status.NEW
    assert incoming_message.internal_notes == ""


@pytest.mark.parametrize("route", ["message_detail", "message_action", "message_delete"])
def test_staff_without_contact_permissions_cannot_access_a_message(client, incoming_message, route):
    user = User.objects.create_user(username="sin-mensajes", is_staff=True)
    user.groups.clear()
    client.force_login(user)
    url = reverse(f"panel:{route}", args=[incoming_message.pk])

    assert client.post(url, {"action": "close"}).status_code == 403
    if route != "message_action":
        assert client.get(url).status_code == 403
    incoming_message.refresh_from_db()
    assert incoming_message.status == ContactMessage.Status.NEW


def test_message_review_updates_only_workflow_fields(admin_client, admin_user, incoming_message):
    response = admin_client.post(
        reverse("panel:message_detail", args=[incoming_message.pk]),
        {
            "status": ContactMessage.Status.IN_PROGRESS,
            "assigned_to": str(admin_user.pk),
            "internal_notes": "Se llamó para dar seguimiento.",
            "name": "Nombre cambiado",
            "email": "otro@example.com",
            "phone": "11111111",
            "kind": ContactMessage.Kind.CONTACT,
            "subject": "Asunto manipulado",
            "message": "Texto manipulado",
            "privacy_accepted": "",
            "source_ip": "192.0.2.99",
        },
    )

    assert response.status_code == 302
    incoming_message.refresh_from_db()
    assert incoming_message.status == ContactMessage.Status.IN_PROGRESS
    assert incoming_message.assigned_to == admin_user
    assert incoming_message.internal_notes == "Se llamó para dar seguimiento."
    assert incoming_message.name == "María López"
    assert incoming_message.email == "maria@example.com"
    assert incoming_message.phone == "+502 4171-3008"
    assert incoming_message.kind == ContactMessage.Kind.PRAYER
    assert incoming_message.subject == "Oración por nuestra familia"
    assert incoming_message.message == "Una petición privada que solo debe leer el equipo."
    assert incoming_message.privacy_accepted is True
    assert incoming_message.source_ip == "192.0.2.10"


@pytest.mark.parametrize("account_state", ["inactive", "nonstaff"])
def test_message_cannot_be_assigned_to_an_account_without_panel_access(
    admin_client, incoming_message, account_state
):
    user = User.objects.create_user(
        username="responsable-invalido",
        is_active=account_state != "inactive",
        is_staff=account_state != "nonstaff",
    )
    response = admin_client.post(
        reverse("panel:message_detail", args=[incoming_message.pk]),
        {"status": "IN_PROGRESS", "assigned_to": str(user.pk), "internal_notes": "Seguimiento"},
    )

    assert response.status_code == 200
    incoming_message.refresh_from_db()
    assert incoming_message.assigned_to is None
    assert incoming_message.status == ContactMessage.Status.NEW
    assert incoming_message.internal_notes == ""


@pytest.mark.parametrize(
    ("action", "status"),
    [
        ("assign", ContactMessage.Status.NEW),
        ("in_progress", ContactMessage.Status.IN_PROGRESS),
        ("close", ContactMessage.Status.CLOSED),
        ("spam", ContactMessage.Status.SPAM),
    ],
)
def test_message_workflow_actions_assign_current_user_when_unassigned(
    admin_client, admin_user, incoming_message, action, status
):
    response = admin_client.post(
        reverse("panel:message_action", args=[incoming_message.pk]), {"action": action}
    )

    assert response.status_code == 302
    incoming_message.refresh_from_db()
    assert incoming_message.status == status
    assert incoming_message.assigned_to == admin_user
    log = LogEntry.objects.get(
        object_id=str(incoming_message.pk), content_type__app_label="contacts"
    )
    assert log.user_id == admin_user.pk
    assert not LogEntry.objects.filter(change_message__contains=incoming_message.message).exists()


def test_reopening_message_preserves_its_responsible_user(admin_client, incoming_message):
    responsible = User.objects.create_user(username="responsable", is_staff=True)
    incoming_message.status = ContactMessage.Status.CLOSED
    incoming_message.assigned_to = responsible
    incoming_message.save()

    response = admin_client.post(
        reverse("panel:message_action", args=[incoming_message.pk]), {"action": "new"}
    )

    assert response.status_code == 302
    incoming_message.refresh_from_db()
    assert incoming_message.status == ContactMessage.Status.NEW
    assert incoming_message.assigned_to == responsible


def test_invalid_message_action_is_rejected_without_mutation(admin_client, incoming_message):
    response = admin_client.post(
        reverse("panel:message_action", args=[incoming_message.pk]),
        {"action": "delete", "status": "CLOSED", "assigned_to": "99999"},
    )

    assert response.status_code == 400
    incoming_message.refresh_from_db()
    assert incoming_message.status == ContactMessage.Status.NEW
    assert incoming_message.assigned_to is None


def test_message_actions_cannot_be_triggered_by_links(admin_client, incoming_message):
    response = admin_client.get(
        reverse("panel:message_action", args=[incoming_message.pk]), {"action": "close"}
    )

    assert response.status_code == 405
    incoming_message.refresh_from_db()
    assert incoming_message.status == ContactMessage.Status.NEW


@pytest.mark.parametrize("route", ["message_detail", "message_action", "message_delete"])
def test_message_mutations_require_csrf(admin_user, incoming_message, route):
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)

    response = client.post(
        reverse(f"panel:{route}", args=[incoming_message.pk]), {"action": "close"}
    )

    assert response.status_code == 403
    assert ContactMessage.objects.filter(pk=incoming_message.pk, status="NEW").exists()


def test_message_list_and_export_use_the_same_combined_filters(admin_client, incoming_message):
    ContactMessage.objects.create(
        name="Otra familia",
        email="otra@example.com",
        subject="Oración ya atendida",
        message="Otra petición",
        kind=ContactMessage.Kind.PRAYER,
        status=ContactMessage.Status.CLOSED,
    )
    ContactMessage.objects.create(
        name="Consulta general",
        email="consulta@example.com",
        subject="Consulta sin relación",
        message="Pregunta de contacto",
        kind=ContactMessage.Kind.CONTACT,
    )
    filters = {"q": "4171-3008", "status": "NEW", "kind": "PRAYER"}

    response = admin_client.get(reverse("panel:message_list"), filters)
    content = response.content.decode()
    assert incoming_message.subject in content
    assert "Oración ya atendida" not in content
    assert "Consulta sin relación" not in content

    rows = csv_rows(admin_client.get(reverse("panel:message_export"), filters))
    assert len(rows) == 2
    assert incoming_message.subject in rows[1]
    assert incoming_message.phone in rows[1] or "'" + incoming_message.phone in rows[1]


@pytest.mark.parametrize(
    "payload",
    ["=HYPERLINK(1)", "+SUM(1)", "-SUM(1)", "@SUM(1)", "  =SUM(1)", "\t=SUM(1)", "\r=SUM(1)"],
)
def test_message_csv_neutralizes_spreadsheet_formulas(admin_client, incoming_message, payload):
    incoming_message.name = payload
    incoming_message.subject = payload
    incoming_message.message = payload
    incoming_message.save()

    rows = csv_rows(admin_client.get(reverse("panel:message_export")))

    assert len(rows) == 2
    assert sum(cell.startswith("'") and cell[1:] == payload for cell in rows[1]) >= 3


def test_messages_are_escaped_when_rendered_in_panel(admin_client, incoming_message):
    incoming_message.name = '<img src=x onerror="alert(1)">'
    incoming_message.subject = '<script>alert("subject")</script>'
    incoming_message.message = '<script>alert("message")</script>'
    incoming_message.save()

    for route, args in (("message_list", []), ("message_detail", [incoming_message.pk])):
        content = admin_client.get(reverse(f"panel:{route}", args=args)).content.decode()
        assert incoming_message.name not in content
        assert incoming_message.subject not in content
        assert incoming_message.message not in content
        assert "&lt;script&gt;" in content


def test_message_delete_requires_confirmation_and_removes_existing_record(
    admin_client, incoming_message
):
    url = reverse("panel:message_delete", args=[incoming_message.pk])

    assert admin_client.get(url).status_code == 200
    assert ContactMessage.objects.filter(pk=incoming_message.pk).exists()

    response = admin_client.post(url)

    assert response.status_code == 302
    assert not ContactMessage.objects.filter(pk=incoming_message.pk).exists()


def test_read_permission_does_not_allow_deleting_messages(client, message_viewer, incoming_message):
    client.force_login(message_viewer)
    url = reverse("panel:message_delete", args=[incoming_message.pk])

    assert client.get(url).status_code == 403
    assert client.post(url).status_code == 403
    assert ContactMessage.objects.filter(pk=incoming_message.pk).exists()
