import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.accounts.roles import CHURCH_ADMIN, COLLABORATOR
from apps.contacts.models import ContactMessage
from apps.core.models import SiteConfiguration
from apps.news.models import Post

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def team_member():
    return User.objects.create_user(
        username="equipo-iglesia",
        password="Betesda-Clave-2026!",
        first_name="María",
        email="maria@example.com",
        is_staff=True,
    )


def test_superuser_creates_staff_account_without_accepting_privilege_spoofing(admin_client):
    response = admin_client.post(
        reverse("panel:user_create"),
        {
            "username": "nueva-editora",
            "first_name": "Ana",
            "last_name": "Pérez",
            "email": "ana@example.com",
            "password1": "Betesda-Nueva-2026!",
            "password2": "Betesda-Nueva-2026!",
            "is_active": "on",
            "is_superuser": "on",
            "is_staff": "",
            "roles": ["Rol inventado"],
            "groups": ["1"],
            "user_permissions": ["1"],
        },
    )

    assert response.status_code == 200
    assert not User.objects.filter(username="nueva-editora").exists()

    response = admin_client.post(
        reverse("panel:user_create"),
        {
            "username": "nueva-editora",
            "first_name": "Ana",
            "last_name": "Pérez",
            "email": "ana@example.com",
            "password1": "Betesda-Nueva-2026!",
            "password2": "Betesda-Nueva-2026!",
            "is_active": "on",
            "is_superuser": "on",
            "is_staff": "",
            "roles": [COLLABORATOR.name],
            "groups": ["1"],
            "user_permissions": ["1"],
        },
    )

    assert response.status_code == 302
    user = User.objects.get(username="nueva-editora")
    assert user.is_staff is True
    assert user.is_superuser is False
    assert user.role_names == [COLLABORATOR.name]
    assert user.first_name == "Ana"
    assert user.check_password("Betesda-Nueva-2026!")
    assert user.user_permissions.count() == 0


@pytest.mark.parametrize(
    ("first_password", "second_password"),
    [("123", "123"), ("Betesda-Nueva-2026!", "Otra-Clave-2026!")],
)
def test_account_creation_rejects_weak_or_mismatched_passwords(
    admin_client, first_password, second_password
):
    response = admin_client.post(
        reverse("panel:user_create"),
        {
            "username": "cuenta-invalida",
            "password1": first_password,
            "password2": second_password,
            "is_active": "on",
        },
    )

    assert response.status_code == 200
    assert not User.objects.filter(username="cuenta-invalida").exists()


@pytest.mark.parametrize("route", ["user_edit", "user_delete", "user_password"])
def test_principal_superuser_accounts_are_protected_from_management_urls(
    admin_client, admin_user, route
):
    url = reverse(f"panel:{route}", args=[admin_user.pk])

    assert admin_client.get(url).status_code in (403, 404)
    assert admin_client.post(url, {"is_active": "", "is_superuser": ""}).status_code in (403, 404)
    admin_user.refresh_from_db()
    assert admin_user.is_active is True
    assert admin_user.is_superuser is True


@pytest.mark.parametrize("route", ["user_edit", "user_delete", "user_password"])
def test_regular_staff_cannot_manage_other_accounts(client, team_member, admin_user, route):
    team_member.user_permissions.add(*Permission.objects.filter(content_type__app_label="accounts"))
    client.force_login(team_member)
    url = reverse(f"panel:{route}", args=[admin_user.pk])

    assert client.get(url).status_code == 403
    assert client.post(url, {"is_active": ""}).status_code == 403


def test_user_edit_cannot_elevate_regular_staff_to_superuser(admin_client, team_member):
    response = admin_client.post(
        reverse("panel:user_edit", args=[team_member.pk]),
        {
            "username": team_member.username,
            "first_name": "María actualizada",
            "last_name": "López",
            "email": "actualizada@example.com",
            "is_active": "on",
            "is_superuser": "on",
            "is_staff": "",
            "password": "una-clave-manipulada",
        },
    )

    assert response.status_code == 302
    team_member.refresh_from_db()
    assert team_member.first_name == "María actualizada"
    assert team_member.is_superuser is False
    assert team_member.is_staff is True
    assert team_member.check_password("Betesda-Clave-2026!")


def test_own_profile_cannot_change_account_identity_or_privileges(client, team_member):
    client.force_login(team_member)

    response = client.post(
        reverse("panel:account"),
        {
            "first_name": "María actualizada",
            "last_name": "López",
            "email": "actualizada@example.com",
            "username": "cuenta-manipulada",
            "roles": [CHURCH_ADMIN.name],
            "is_superuser": "on",
            "is_staff": "",
            "is_active": "",
        },
    )

    assert response.status_code == 302
    team_member.refresh_from_db()
    assert team_member.first_name == "María actualizada"
    assert team_member.email == "actualizada@example.com"
    assert team_member.username == "equipo-iglesia"
    assert team_member.role_names == []
    assert team_member.is_superuser is False
    assert team_member.is_staff is True
    assert team_member.is_active is True


def test_own_password_change_requires_current_password(client, team_member):
    client.force_login(team_member)

    response = client.post(
        reverse("panel:password_change"),
        {
            "old_password": "Clave-Incorrecta-2026!",
            "new_password1": "Betesda-Actualizada-2026!",
            "new_password2": "Betesda-Actualizada-2026!",
        },
    )

    assert response.status_code == 200
    team_member.refresh_from_db()
    assert team_member.check_password("Betesda-Clave-2026!")


def test_own_password_change_preserves_current_authenticated_session(client, team_member):
    client.force_login(team_member)

    response = client.post(
        reverse("panel:password_change"),
        {
            "old_password": "Betesda-Clave-2026!",
            "new_password1": "Betesda-Actualizada-2026!",
            "new_password2": "Betesda-Actualizada-2026!",
        },
    )

    assert response.status_code == 302
    team_member.refresh_from_db()
    assert team_member.check_password("Betesda-Actualizada-2026!")
    assert not team_member.check_password("Betesda-Clave-2026!")
    assert int(client.session["_auth_user_id"]) == team_member.pk
    assert client.get(reverse("panel:dashboard")).status_code == 200


def test_superuser_can_reset_regular_staff_password(admin_client, team_member):
    response = admin_client.post(
        reverse("panel:user_password", args=[team_member.pk]),
        {
            "new_password1": "Betesda-Reestablecida-2026!",
            "new_password2": "Betesda-Reestablecida-2026!",
        },
    )

    assert response.status_code == 302
    team_member.refresh_from_db()
    assert team_member.check_password("Betesda-Reestablecida-2026!")


def test_configuration_changes_update_singleton_shared_with_public_site(admin_client, client):
    data = {
        "institution_name": "Betesda Rosa de Sarón",
        "slogan": "Un lugar para tu familia",
        "phone": "4171-3008",
        "email": "contacto@example.com",
        "address": "Dirección actualizada del templo",
        "facebook_url": "https://www.facebook.com/betesda",
        "map_url": "https://maps.app.goo.gl/sSZMK48Ky8Mg1jSH6",
    }
    assert admin_client.post(reverse("panel:settings"), data).status_code == 302
    configuration = SiteConfiguration.objects.get()
    data["phone"] = "5555-8888"

    assert admin_client.post(reverse("panel:settings"), data).status_code == 302
    configuration.refresh_from_db()
    assert SiteConfiguration.objects.count() == 1
    assert configuration.phone == "5555-8888"
    assert "5555-8888" in client.get(reverse("contacts:contact")).content.decode()


def test_configuration_rejects_invalid_contact_urls(admin_client):
    response = admin_client.post(
        reverse("panel:settings"),
        {
            "institution_name": "Betesda Rosa de Sarón",
            "email": "correo-invalido",
            "facebook_url": "javascript:alert(1)",
            "map_url": "javascript:alert(1)",
        },
    )

    assert response.status_code == 200
    assert not SiteConfiguration.objects.exists()


def test_configuration_read_permission_does_not_grant_write_access(client):
    user = User.objects.create_user(username="config-lectura", is_staff=True)
    user.groups.clear()
    user.user_permissions.set(
        Permission.objects.filter(content_type__app_label="core", codename="view_siteconfiguration")
    )
    client.force_login(user)

    assert client.get(reverse("panel:settings")).status_code == 200
    response = client.post(reverse("panel:settings"), {"institution_name": "Manipulada"})

    assert response.status_code == 403
    assert not SiteConfiguration.objects.exists()


def test_deleting_staff_preserves_received_messages_and_requires_confirmation(
    admin_client, team_member
):
    message = ContactMessage.objects.create(
        name="Lucía",
        email="lucia@example.com",
        subject="Consulta",
        message="Mensaje privado",
        assigned_to=team_member,
    )
    url = reverse("panel:user_delete", args=[team_member.pk])

    assert admin_client.get(url).status_code == 200
    assert User.objects.filter(pk=team_member.pk).exists()
    assert admin_client.post(url).status_code == 302

    assert not User.objects.filter(pk=team_member.pk).exists()
    message.refresh_from_db()
    assert message.assigned_to is None
    assert message.message == "Mensaje privado"


def test_author_cannot_be_deleted_and_news_is_preserved(admin_client, team_member):
    post = Post.objects.create(
        title="Noticia de la comunidad", excerpt="Resumen", body="Contenido", author=team_member
    )

    response = admin_client.post(reverse("panel:user_delete", args=[team_member.pk]))

    assert response.status_code == 302
    assert response.url == reverse("panel:user_edit", args=[team_member.pk])
    assert User.objects.filter(pk=team_member.pk).exists()
    post.refresh_from_db()
    assert post.author_id == team_member.pk


@pytest.mark.parametrize("operation", ["profile", "password_change", "password_reset"])
def test_personal_updates_do_not_grant_additional_role_permissions(
    client, admin_client, team_member, operation
):
    team_member.groups.clear()
    team_member.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="contacts", codename="view_contactmessage"
        )
    )
    client.force_login(team_member)
    if operation == "profile":
        response = client.post(
            reverse("panel:account"),
            {"first_name": "María", "last_name": "López", "email": "maria@example.com"},
        )
    else:
        data = {
            "new_password1": "Betesda-Actualizada-2026!",
            "new_password2": "Betesda-Actualizada-2026!",
        }
        if operation == "password_change":
            data["old_password"] = "Betesda-Clave-2026!"
            response = client.post(reverse("panel:password_change"), data)
        else:
            response = admin_client.post(
                reverse("panel:user_password", args=[team_member.pk]), data
            )

    assert response.status_code == 302
    current = User.objects.get(pk=team_member.pk)
    assert current.has_perm("contacts.view_contactmessage") is True
    assert current.has_perm("contacts.change_contactmessage") is False
    assert current.groups.count() == 0
