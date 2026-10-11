import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from apps.contacts.models import ContactMessage

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def panel_staff():
    return User.objects.create_user(
        username="panel-equipo", password="Betesda-Prueba-2026!", is_staff=True
    )


@pytest.fixture
def restricted_staff():
    user = User.objects.create_user(
        username="panel-limitado", password="Betesda-Prueba-2026!", is_staff=True
    )
    user.groups.clear()
    user.user_permissions.clear()
    return user


@pytest.mark.parametrize(
    "route",
    [
        "dashboard",
        "message_list",
        "event_list",
        "news_list",
        "album_list",
        "settings",
        "user_list",
        "activity",
        "account",
    ],
)
def test_anonymous_panel_access_requires_login(client, route):
    response = client.get(reverse(f"panel:{route}"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("panel:login") + "?next=")


def test_active_staff_can_login_with_existing_django_credentials(client, panel_staff):
    response = client.post(
        reverse("panel:login"),
        {"username": panel_staff.username, "password": "Betesda-Prueba-2026!"},
    )

    assert response.status_code == 302
    assert response.url == reverse("panel:dashboard")
    assert int(client.session["_auth_user_id"]) == panel_staff.pk
    assert client.get(reverse("panel:dashboard")).status_code == 200


@pytest.mark.parametrize("account_state", ["nonstaff", "inactive"])
def test_login_rejects_accounts_without_panel_access(client, account_state):
    user = User.objects.create_user(
        username="sin-panel",
        password="Betesda-Prueba-2026!",
        is_staff=account_state == "inactive",
        is_active=account_state != "inactive",
    )

    response = client.post(
        reverse("panel:login"),
        {"username": user.username, "password": "Betesda-Prueba-2026!"},
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_authenticated_nonstaff_account_cannot_enter_panel(client):
    user = User.objects.create_user(username="visitante", is_staff=False)
    client.force_login(user)

    response = client.get(reverse("panel:dashboard"))

    assert response.status_code in (302, 403)


@pytest.mark.parametrize(
    "next_url", ["https://example.com/", "//example.com/", "http://testserver/"]
)
def test_login_cannot_redirect_to_an_external_destination(client, panel_staff, next_url):
    response = client.post(
        reverse("panel:login") + "?next=" + next_url,
        {"username": panel_staff.username, "password": "Betesda-Prueba-2026!"},
        secure=True,
    )

    assert response.status_code == 302
    assert response.url == reverse("panel:dashboard")


def test_login_can_return_to_a_local_panel_destination(client, panel_staff):
    destination = reverse("panel:message_list") + "?estado=NEW"
    response = client.post(
        reverse("panel:login"),
        {
            "username": panel_staff.username,
            "password": "Betesda-Prueba-2026!",
            "next": destination,
        },
    )

    assert response.status_code == 302
    assert response.url == destination


@pytest.mark.parametrize(
    "route", ["message_list", "event_list", "news_list", "album_list", "settings"]
)
def test_staff_without_model_permission_cannot_open_sections(client, restricted_staff, route):
    client.force_login(restricted_staff)

    response = client.get(reverse(f"panel:{route}"))

    assert response.status_code == 403


def test_dashboard_does_not_disclose_messages_without_read_permission(client, restricted_staff):
    ContactMessage.objects.create(
        name="Privada",
        email="privada@example.com",
        subject="Solicitud confidencial",
        message="Privado",
    )
    client.force_login(restricted_staff)

    response = client.get(reverse("panel:dashboard"))

    assert response.status_code == 200
    assert "Solicitud confidencial" not in response.content.decode()
    assert "privada@example.com" not in response.content.decode()
    assert reverse("panel:message_list") not in response.content.decode()


@pytest.mark.parametrize("route", ["dashboard", "message_list", "message_export", "account"])
def test_private_panel_responses_are_not_cached(client, panel_staff, route):
    client.force_login(panel_staff)

    response = client.get(reverse(f"panel:{route}"))

    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]


def test_logout_requires_post_and_ends_only_current_session(client, panel_staff):
    client.force_login(panel_staff)

    assert client.get(reverse("panel:logout")).status_code == 405
    assert "_auth_user_id" in client.session

    response = client.post(reverse("panel:logout"))

    assert response.status_code == 302
    assert "_auth_user_id" not in client.session
    assert client.get(reverse("panel:dashboard")).status_code == 302


@pytest.mark.parametrize(
    "route",
    [
        "login",
        "logout",
        "event_create",
        "news_create",
        "album_create",
        "settings",
        "user_create",
        "account",
        "password_change",
    ],
)
def test_panel_mutations_require_a_csrf_token(admin_user, route):
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)

    response = client.post(reverse(f"panel:{route}"), {})

    assert response.status_code == 403


@pytest.mark.parametrize("role", [User.Role.ADMIN, User.Role.EDITOR])
@pytest.mark.parametrize("route", ["user_list", "user_create", "activity"])
def test_account_management_and_audit_require_superuser_even_with_permissions(client, role, route):
    user = User.objects.create_user(username=f"responsable-{role}", is_staff=True, role=role)
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label__in=("accounts", "admin"))
    )
    client.force_login(user)

    assert client.get(reverse(f"panel:{route}")).status_code == 403


def test_deactivating_an_existing_staff_account_revokes_panel_access(client, panel_staff):
    client.force_login(panel_staff)
    assert client.get(reverse("panel:dashboard")).status_code == 200
    User.objects.filter(pk=panel_staff.pk).update(is_active=False)

    assert client.get(reverse("panel:dashboard")).status_code == 302


def test_activity_is_read_only_even_for_superuser(admin_client):
    assert admin_client.get(reverse("panel:activity")).status_code == 200
    assert admin_client.post(reverse("panel:activity"), {"action": "delete"}).status_code == 405
