import pytest
from django.test import Client
from django.urls import reverse

from apps.contacts.models import ContactMessage

pytestmark = pytest.mark.django_db


@pytest.fixture
def contact_data():
    return {
        "kind": ContactMessage.Kind.CONTACT,
        "name": "  María López  ",
        "email": "maria@example.com",
        "subject": "Petición de oración",
        "message": "Quisiera solicitar oración por mi familia.",
        "privacy_accepted": "on",
        "website": "",
    }


def test_contact_page_shows_public_contact_form(client):
    response = client.get(reverse("contacts:contact"), {"tipo": "contacto"})
    content = response.content.decode()

    assert response.status_code == 200
    assert 'action="/contacto/enviar/#formulario"' in content
    assert 'name="csrfmiddlewaretoken"' in content
    assert "Enviar mensaje" in content
    for field in ("name", "email", "phone", "subject", "message", "privacy_accepted"):
        assert f'name="{field}"' in content
    assert "css/contact.css" in content
    assert "Deja este campo vacío" not in content
    assert '<div hidden aria-hidden="true">' in content
    assert response.context["contact_form"].fields["phone"].required is False
    assert not ContactMessage.objects.exists()


def test_public_submission_creates_new_message(client, contact_data):
    response = client.post(reverse("contacts:send"), contact_data, REMOTE_ADDR="192.0.2.10")

    assert response.status_code == 302
    assert response.url == f"{reverse('contacts:contact')}?tipo=contacto#formulario"
    message = ContactMessage.objects.get()
    assert message.name == "María López"
    assert message.email == contact_data["email"]
    assert message.phone == ""
    assert message.subject == contact_data["subject"]
    assert message.message == contact_data["message"]
    assert message.privacy_accepted is True
    assert message.source_ip == "192.0.2.10"
    assert message.status == ContactMessage.Status.NEW
    assert message.kind == ContactMessage.Kind.CONTACT
    assert message.assigned_to is None
    assert message.internal_notes == ""


@pytest.mark.parametrize("phone", ["+502 4171-3008", "4171-3008", "(502) 4171 3008", ""])
def test_submission_accepts_optional_phone(client, contact_data, phone):
    contact_data["phone"] = phone

    response = client.post(reverse("contacts:send"), contact_data)

    assert response.status_code == 302
    assert ContactMessage.objects.get().phone == phone


def test_submission_cannot_set_administrative_fields(client, contact_data, admin_user):
    contact_data.update(
        status=ContactMessage.Status.CLOSED,
        assigned_to=str(admin_user.pk),
        internal_notes="Nota manipulada",
        source_ip="192.0.2.99",
    )

    response = client.post(
        reverse("contacts:send"),
        contact_data,
        REMOTE_ADDR="192.0.2.10",
        HTTP_X_FORWARDED_FOR="192.0.2.99",
    )

    assert response.status_code == 302
    message = ContactMessage.objects.get()
    assert message.status == ContactMessage.Status.NEW
    assert message.assigned_to is None
    assert message.internal_notes == ""
    assert message.source_ip == "192.0.2.10"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "   "),
        ("name", "a" * 121),
        ("email", ""),
        ("email", "correo-invalido"),
        ("phone", "no-es-un-telefono"),
        ("phone", "123"),
        ("phone", "1" * 16),
        ("phone", "1" * 31),
        ("subject", ""),
        ("subject", "a" * 181),
        ("message", ""),
        ("message", "   "),
        ("message", "a" * 5001),
        ("privacy_accepted", ""),
        ("kind", "invalid-kind"),
        ("kind", ""),
    ],
)
def test_invalid_submission_keeps_input_and_does_not_save(client, contact_data, field, value):
    contact_data[field] = value

    response = client.post(reverse("contacts:send"), contact_data)

    assert response.status_code == 200
    form = response.context["contact_form"]
    assert field in form.errors
    assert form.is_bound
    assert form["subject"].value() == contact_data["subject"]
    assert 'role="alert"' in response.content.decode()
    assert not ContactMessage.objects.exists()


def test_missing_consent_is_rejected(client, contact_data):
    del contact_data["privacy_accepted"]

    response = client.post(reverse("contacts:send"), contact_data)

    assert "privacy_accepted" in response.context["contact_form"].errors
    assert not ContactMessage.objects.exists()


def test_honeypot_rejects_spam(client, contact_data):
    contact_data["website"] = "https://spam.example.com"

    response = client.post(reverse("contacts:send"), contact_data)

    assert response.status_code == 200
    assert response.context["contact_form"].non_field_errors()
    assert not ContactMessage.objects.exists()


def test_success_confirmation_and_refresh_do_not_resubmit(client, contact_data):
    response = client.post(reverse("contacts:send"), contact_data, follow=True)

    assert response.status_code == 200
    assert "Recibimos tu mensaje" in response.content.decode()
    assert not response.context["contact_form"].is_bound

    response = client.get(reverse("contacts:contact"))

    assert "Recibimos tu mensaje" not in response.content.decode()
    assert ContactMessage.objects.count() == 1
    assert contact_data["email"] not in response.content.decode()
    assert contact_data["message"] not in response.content.decode()


def test_contact_endpoint_only_accepts_post(client):
    response = client.get(reverse("contacts:send"))

    assert response.status_code == 405
    assert not ContactMessage.objects.exists()


@pytest.mark.parametrize("kind", [ContactMessage.Kind.CONTACT, ContactMessage.Kind.PRAYER])
@pytest.mark.parametrize("route", ["contacts:send", "contacts:contact"])
def test_contact_form_enforces_csrf(contact_data, kind, route):
    client = Client(enforce_csrf_checks=True)
    contact_data["kind"] = kind

    response = client.post(reverse(route), contact_data)

    assert response.status_code == 403
    assert not ContactMessage.objects.exists()

    client.get(reverse("contacts:contact"))
    contact_data["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
    response = client.post(reverse(route), contact_data)

    assert response.status_code == 302
    assert ContactMessage.objects.count() == 1


def test_submitted_message_appears_in_backoffice(client, admin_client, contact_data):
    contact_data["phone"] = "+502 4171-3008"
    client.post(reverse("contacts:send"), contact_data)
    message = ContactMessage.objects.get()

    response = admin_client.get(reverse("admin:index"))

    assert response.context["bo_new_messages"] == 1
    message_kpi = next(
        item for item in response.context["dashboard"]["kpis"] if item["label"] == "Mensajes nuevos"
    )
    assert message_kpi["value"] == 1
    assert message.subject in response.content.decode()

    response = admin_client.get(
        reverse("admin:contacts_contactmessage_changelist"), {"status__exact": "NEW"}
    )
    assert message in response.context["cl"].queryset

    response = admin_client.get(reverse("admin:contacts_contactmessage_change", args=[message.pk]))
    assert message.email in response.content.decode()
    assert message.phone in response.content.decode()
    assert message.message in response.content.decode()


def test_backoffice_can_search_and_export_phone(client, admin_client, contact_data):
    contact_data["phone"] = "+502 4171-3008"
    client.post(reverse("contacts:send"), contact_data)
    message = ContactMessage.objects.get()
    url = reverse("admin:contacts_contactmessage_changelist")

    response = admin_client.get(url, {"q": "4171-3008"})

    assert message in response.context["cl"].queryset
    assert message.phone in response.content.decode()

    response = admin_client.post(url, {"action": "export_csv", "_selected_action": [message.pk]})

    assert response["Content-Type"].startswith("text/csv")
    assert message.phone in response.content.decode("utf-8-sig")


def test_validation_errors_preserve_prayer_mode_and_input(client, contact_data):
    contact_data["kind"] = ContactMessage.Kind.PRAYER
    contact_data["email"] = "correo-invalido"

    response = client.post(reverse("contacts:send"), contact_data)

    assert response.context["contact_mode"]["kind"] == ContactMessage.Kind.PRAYER
    assert response.context["contact_form"]["subject"].value() == contact_data["subject"]
    assert "Motivo de la oración" in response.content.decode()
    assert "contacts/contact.html" in [template.name for template in response.templates]
    assert not ContactMessage.objects.exists()


def test_validation_response_escapes_message_content(client, contact_data):
    contact_data["email"] = "correo-invalido"
    contact_data["message"] = '<script>alert("test")</script>'

    response = client.post(reverse("contacts:send"), contact_data)
    content = response.content.decode()

    assert "<script>" not in content
    assert "&lt;script&gt;" in content
    assert not ContactMessage.objects.exists()


@pytest.mark.parametrize(
    ("kind", "slug", "label", "confirmation"),
    [
        (
            ContactMessage.Kind.PRAYER,
            "oracion",
            "Motivo de la oración",
            "Recibimos tu petición de oración",
        ),
        (ContactMessage.Kind.CONTACT, "contacto", "Asunto del mensaje", "Recibimos tu mensaje"),
    ],
)
def test_each_contact_tab_has_correct_copy_and_stores_kind(
    client, admin_client, contact_data, kind, slug, label, confirmation
):
    response = client.get(reverse("contacts:contact"), {"tipo": slug})
    assert label in response.content.decode()
    assert response.context["contact_form"]["kind"].value() == kind
    contact_data["kind"] = kind

    response = client.post(reverse("contacts:send"), contact_data, follow=True)

    message = ContactMessage.objects.get()
    assert message.kind == kind
    assert message.status == ContactMessage.Status.NEW
    assert confirmation in response.content.decode()
    assert response.context["contact_mode"]["kind"] == kind
    admin_response = admin_client.get(
        reverse("admin:contacts_contactmessage_changelist"), {"kind__exact": kind}
    )
    assert message in admin_response.context["cl"].queryset
    assert message.get_kind_display() in admin_response.content.decode()
