import io
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.roles import ADMIN_GROUP, EDITOR_GROUP
from apps.backoffice.dashboard import _weekly_message_counts
from apps.contacts.models import ContactMessage
from apps.core.models import SiteConfiguration
from apps.events.models import Event
from apps.gallery.models import Album, Photo
from apps.news.models import Post

User = get_user_model()


def make_event(**overrides) -> Event:
    data = {
        "title": "Culto de jóvenes",
        "summary": "Reunión semanal",
        "description": "Alabanza y enseñanza.",
        "starts_at": timezone.now() + timedelta(days=2),
        "location": "Templo principal",
    }
    data.update(overrides)
    return Event.objects.create(**data)


def make_message(**overrides) -> ContactMessage:
    data = {
        "name": "María López",
        "email": "maria@example.com",
        "subject": "Horarios de servicio",
        "message": "¿A qué hora son los servicios?",
    }
    data.update(overrides)
    return ContactMessage.objects.create(**data)


def png_file(name: str = "foto.png") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "gold").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@pytest.fixture
def editor(db):
    return User.objects.create_user(
        username="editor", password="x-test-pass", role=User.Role.EDITOR, is_staff=True
    )


@pytest.fixture
def role_admin(db):
    return User.objects.create_user(
        username="coordinadora", password="x-test-pass", role=User.Role.ADMIN, is_staff=True
    )


# --- Tablero --------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_renders_for_superuser(admin_client):
    response = admin_client.get(reverse("admin:index"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Hola," in content
    assert "Gestión del sitio" in content
    assert "Todas las secciones" not in content
    assert "admin/app_list.html" not in content


@pytest.mark.django_db
def test_dashboard_shows_new_messages_and_bell(admin_client):
    make_message()

    content = admin_client.get(reverse("admin:index")).content.decode()

    assert "Mensajes nuevos" in content
    assert "1 nuevo" in content
    assert "Horarios de servicio" in content


@pytest.mark.django_db
def test_dashboard_warns_when_there_are_no_upcoming_events(admin_client):
    content = admin_client.get(reverse("admin:index")).content.decode()

    assert "No hay eventos próximos publicados" in content
    assert "Falta la configuración general del sitio" in content


@pytest.mark.django_db
def test_weekly_message_counts_has_eight_buckets_and_counts_current_week():
    make_message()

    buckets = _weekly_message_counts(timezone.now())

    assert len(buckets) == 8
    assert buckets[-1]["count"] == 1
    assert all(bucket["count"] == 0 for bucket in buckets[:-1])


@pytest.mark.django_db
def test_activity_log_is_read_only(admin_client):
    response = admin_client.get(reverse("admin:admin_logentry_changelist"))
    add_response = admin_client.get(reverse("admin:admin_logentry_add"))

    assert response.status_code == 200
    assert add_response.status_code == 403


# --- Roles y permisos --------------------------------------------------------------------


@pytest.mark.django_db
def test_user_is_placed_in_group_matching_role(editor, role_admin):
    assert list(editor.groups.values_list("name", flat=True)) == [EDITOR_GROUP]
    assert list(role_admin.groups.values_list("name", flat=True)) == [ADMIN_GROUP]


@pytest.mark.django_db
def test_changing_role_swaps_group(editor):
    editor.role = User.Role.ADMIN
    editor.save()

    assert list(editor.groups.values_list("name", flat=True)) == [ADMIN_GROUP]


@pytest.mark.django_db
def test_setup_roles_command_defines_permissions():
    call_command("setup_roles")

    editors = Group.objects.get(name=EDITOR_GROUP)
    codenames = set(editors.permissions.values_list("codename", flat=True))
    assert "change_event" in codenames
    assert "delete_event" in codenames
    assert "delete_post" in codenames
    assert "delete_album" in codenames
    assert "delete_contactmessage" in codenames
    assert "view_user" not in codenames
    assert "add_user" not in codenames


@pytest.mark.django_db
def test_editor_can_use_panel_but_not_manage_users(client, editor):
    client.force_login(editor)

    assert client.get(reverse("admin:index")).status_code == 200
    assert client.get(reverse("admin:events_event_changelist")).status_code == 200
    assert client.get(reverse("admin:accounts_user_changelist")).status_code == 403


@pytest.mark.django_db
def test_regular_roles_cannot_manage_users(client, editor, role_admin):
    for user in (editor, role_admin):
        client.force_login(user)
        assert client.get(reverse("admin:accounts_user_changelist")).status_code == 403
        assert client.get(reverse("admin:accounts_user_add")).status_code == 403


@pytest.mark.django_db
def test_superuser_can_create_regular_backoffice_user(admin_client):
    response = admin_client.post(
        reverse("admin:accounts_user_add"),
        {
            "username": "nuevo-equipo",
            "password1": "Betesda-Test-2026!",
            "password2": "Betesda-Test-2026!",
            "first_name": "Nuevo",
            "last_name": "Usuario",
            "email": "nuevo@example.com",
            "is_active": "on",
            "_save": "Guardar",
        },
    )

    assert response.status_code == 302
    created = User.objects.get(username="nuevo-equipo")
    assert created.is_staff is True
    assert created.is_superuser is False
    assert created.role == User.Role.EDITOR


# --- Modelos --------------------------------------------------------------------------------


@pytest.mark.django_db
def test_duplicate_titles_get_unique_slugs():
    first = make_event()
    second = make_event()

    assert first.slug == "culto-de-jovenes"
    assert second.slug == "culto-de-jovenes-2"


@pytest.mark.django_db
def test_event_end_cannot_precede_start():
    start = timezone.now()
    event = Event(
        title="Vigilia",
        summary="Noche de oración",
        description="Oración y alabanza.",
        starts_at=start,
        ends_at=start - timedelta(hours=1),
        location="Templo",
    )

    with pytest.raises(ValidationError) as error:
        event.full_clean()

    assert "ends_at" in error.value.message_dict


# --- Acciones y flujos del admin -------------------------------------------------------------


@pytest.mark.django_db
def test_publish_and_duplicate_event_actions(admin_client):
    event = make_event()
    url = reverse("admin:events_event_changelist")

    admin_client.post(url, {"action": "publish_events", "_selected_action": [event.pk]})
    event.refresh_from_db()
    assert event.is_published is True

    admin_client.post(url, {"action": "duplicate_events", "_selected_action": [event.pk]})
    copy = Event.objects.exclude(pk=event.pk).get()
    assert copy.title.endswith("(copia)")
    assert copy.is_published is False


@pytest.mark.django_db
def test_post_author_is_assigned_automatically(admin_client, admin_user):
    response = admin_client.post(
        reverse("admin:news_post_add"),
        {
            "title": "Aviso importante",
            "slug": "aviso-importante",
            "excerpt": "Resumen breve",
            "body": "Contenido del aviso.",
            "status": Post.Status.DRAFT,
        },
    )

    assert response.status_code == 302
    assert Post.objects.get(slug="aviso-importante").author == admin_user


@pytest.mark.django_db
def test_closing_a_message_assigns_the_responsible_user(admin_client, admin_user):
    message = make_message()

    admin_client.post(
        reverse("admin:contacts_contactmessage_changelist"),
        {"action": "mark_closed", "_selected_action": [message.pk]},
    )

    message.refresh_from_db()
    assert message.status == ContactMessage.Status.CLOSED
    assert message.assigned_to == admin_user


@pytest.mark.django_db
def test_csv_export_is_available_to_regular_backoffice_users(admin_client, client, editor):
    message = make_message(subject="=HYPERLINK(1)")
    url = reverse("admin:contacts_contactmessage_changelist")
    payload = {"action": "export_csv", "_selected_action": [message.pk]}

    response = admin_client.post(url, payload)
    assert response["Content-Type"].startswith("text/csv")
    body = response.content.decode("utf-8-sig")
    assert "María López" in body
    assert "'=HYPERLINK(1)" in body  # fórmulas neutralizadas

    client.force_login(editor)
    response = client.post(url, payload)
    assert response["Content-Type"].startswith("text/csv")


@pytest.mark.django_db
def test_site_configuration_changelist_redirects(admin_client):
    url = reverse("admin:core_siteconfiguration_changelist")

    response = admin_client.get(url)
    assert response.status_code == 302
    assert response.url == reverse("admin:core_siteconfiguration_add")

    config = SiteConfiguration.objects.create(institution_name="Betesda Rosa de Sarón")
    response = admin_client.get(url)
    assert response.url == reverse("admin:core_siteconfiguration_change", args=[config.pk])


@pytest.mark.django_db
def test_bulk_photo_upload(admin_client):
    album = Album.objects.create(title="Aniversario")
    url = reverse("admin:gallery_album_upload_photos", args=[album.pk])

    assert admin_client.get(url).status_code == 200

    response = admin_client.post(
        url,
        {"images": [png_file("a.png"), png_file("b.png")], "alt_text": "Celebración"},
    )

    assert response.status_code == 302
    photos = list(Photo.objects.filter(album=album).order_by("order"))
    assert [photo.order for photo in photos] == [0, 1]
    assert {photo.alt_text for photo in photos} == {"Celebración"}


@pytest.mark.django_db
def test_bulk_photo_upload_rejects_non_images(admin_client):
    album = Album.objects.create(title="Retiro")
    fake = SimpleUploadedFile("nota.png", b"esto no es una imagen", content_type="image/png")

    response = admin_client.post(
        reverse("admin:gallery_album_upload_photos", args=[album.pk]), {"images": [fake]}
    )

    assert response.status_code == 200
    assert Photo.objects.count() == 0
