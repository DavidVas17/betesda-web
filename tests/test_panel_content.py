from datetime import timedelta
from io import BytesIO

import pytest
from django.contrib.admin.models import ADDITION, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.roles import COORDINATOR, set_user_roles
from apps.events.models import Event
from apps.gallery.models import Album, Photo
from apps.news.models import Post

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def content_editor():
    user = User.objects.create_user(username="editor-contenido", is_staff=True)
    set_user_roles(user, [COORDINATOR.name])
    return user


@pytest.fixture
def permission_user():
    def make(*permissions):
        user = User.objects.create_user(username="permisos-limitados", is_staff=True)
        user.groups.clear()
        user.user_permissions.set(Permission.objects.filter(codename__in=permissions))
        return user

    return make


def event_data(**overrides):
    data = {
        "title": "Encuentro de familias",
        "summary": "Un espacio para compartir",
        "description": "Nos reuniremos para orar juntos.",
        "starts_at": "2028-11-15T09:30",
        "ends_at": "2028-11-15T11:00",
        "location": "Templo principal",
    }
    data.update(overrides)
    return data


def make_event(**overrides):
    data = {
        "title": "Encuentro de familias",
        "summary": "Compartamos juntos",
        "description": "Alabanza y enseñanza.",
        "starts_at": timezone.now() + timedelta(days=2),
        "location": "Templo principal",
    }
    data.update(overrides)
    return Event.objects.create(**data)


def post_data(**overrides):
    data = {
        "title": "Anuncio de la comunidad",
        "excerpt": "Información para nuestras familias",
        "body": "Compartimos una noticia con la iglesia.",
        "status": Post.Status.DRAFT,
        "published_at": "",
    }
    data.update(overrides)
    return data


def make_post(author, **overrides):
    data = {
        "title": "Noticia de prueba",
        "excerpt": "Resumen",
        "body": "Contenido",
        "author": author,
    }
    data.update(overrides)
    return Post.objects.create(**data)


def image_file(name="foto.png"):
    output = BytesIO()
    Image.new("RGB", (12, 12), "#446257").save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


def test_panel_event_lifecycle_updates_public_content_and_audit(client, content_editor):
    client.force_login(content_editor)
    response = client.post(reverse("panel:event_create"), event_data(slug="slug-inyectado"))
    assert response.status_code == 302
    event = Event.objects.get()
    assert event.slug != "slug-inyectado"
    assert response.url == reverse("panel:event_edit", args=[event.pk])
    assert timezone.localtime(event.starts_at).strftime("%Y-%m-%dT%H:%M") == "2028-11-15T09:30"
    assert client.get(event.get_absolute_url()).status_code == 404

    action_url = reverse("panel:event_action", args=[event.pk])
    assert client.post(action_url, {"action": "publish"}).status_code == 302
    assert client.get(event.get_absolute_url()).status_code == 200
    assert client.post(action_url, {"action": "feature"}).status_code == 302
    event.refresh_from_db()
    assert event.is_featured
    assert client.post(action_url, {"action": "duplicate"}).status_code == 302
    copy = Event.objects.exclude(pk=event.pk).get()
    assert copy.slug != event.slug
    assert not copy.is_published
    assert not copy.is_featured
    assert copy.summary == event.summary

    delete_url = reverse("panel:event_delete", args=[copy.pk])
    assert client.get(delete_url).status_code == 200
    assert Event.objects.filter(pk=copy.pk).exists()
    assert client.post(delete_url).status_code == 302
    assert not Event.objects.filter(pk=copy.pk).exists()
    assert LogEntry.objects.filter(object_id=str(copy.pk), action_flag=DELETION).exists()
    assert LogEntry.objects.filter(object_id=str(event.pk), action_flag=ADDITION).exists()


def test_event_invalid_date_range_retains_form_input(client, content_editor):
    client.force_login(content_editor)
    response = client.post(reverse("panel:event_create"), event_data(ends_at="2028-11-15T08:00"))
    assert response.status_code == 200
    assert "ends_at" in response.context["form"].errors
    assert response.context["form"]["title"].value() == "Encuentro de familias"
    assert not Event.objects.exists()


def test_news_author_and_slug_cannot_be_spoofed_and_publication_is_shared(
    client, content_editor, admin_user
):
    client.force_login(content_editor)
    response = client.post(
        reverse("panel:news_create"),
        post_data(author=admin_user.pk, slug="slug-ajeno", status=Post.Status.PUBLISHED),
    )
    assert response.status_code == 302
    post = Post.objects.get()
    assert post.author == content_editor
    assert post.slug != "slug-ajeno"
    assert post.published_at is not None
    assert client.get(post.get_absolute_url()).status_code == 200

    client.force_login(admin_user)
    response = client.post(
        reverse("panel:news_edit", args=[post.pk]),
        post_data(title="Título actualizado", author=admin_user.pk, slug="otro-slug"),
    )
    assert response.status_code == 302
    post.refresh_from_db()
    assert post.author == content_editor
    assert post.title == "Título actualizado"
    assert post.slug != "otro-slug"
    assert client.get(post.get_absolute_url()).status_code == 404
    assert (
        client.post(reverse("panel:news_action", args=[post.pk]), {"action": "publish"}).status_code
        == 302
    )
    assert client.get(post.get_absolute_url()).status_code == 200
    assert (
        client.post(reverse("panel:news_action", args=[post.pk]), {"action": "archive"}).status_code
        == 302
    )
    assert client.get(post.get_absolute_url()).status_code == 404


def test_future_news_date_schedules_publication_and_unknown_status_is_rejected(
    client, content_editor
):
    client.force_login(content_editor)
    response = client.post(
        reverse("panel:news_create"),
        post_data(status=Post.Status.PUBLISHED, published_at="2099-01-01T10:00"),
    )
    assert response.status_code == 302
    post = Post.objects.get()
    assert client.get(post.get_absolute_url()).status_code == 404
    response = client.post(
        reverse("panel:news_edit", args=[post.pk]), post_data(status="SUPERADMIN")
    )
    assert response.status_code == 200
    assert "status" in response.context["form"].errors
    post.refresh_from_db()
    assert post.status == Post.Status.PUBLISHED


@pytest.mark.parametrize("upload_type", ["invalid_image", "oversized_image"])
def test_invalid_cover_upload_cannot_create_content(client, content_editor, upload_type):
    client.force_login(content_editor)
    payload = b"not-an-image" if upload_type == "invalid_image" else b"x" * (8 * 1024 * 1024 + 1)
    response = client.post(
        reverse("panel:event_create"),
        event_data(
            cover_image=SimpleUploadedFile("portada.png", payload, content_type="image/png")
        ),
    )
    assert response.status_code == 200
    assert "cover_image" in response.context["form"].errors
    assert not Event.objects.exists()


def test_cover_can_be_uploaded_and_removed_using_form(client, content_editor):
    client.force_login(content_editor)
    response = client.post(reverse("panel:event_create"), event_data(cover_image=image_file()))
    assert response.status_code == 302
    event = Event.objects.get()
    old_image = event.cover_image.name
    storage = event.cover_image.storage
    assert storage.exists(old_image)
    response = client.post(
        reverse("panel:event_edit", args=[event.pk]), event_data(**{"cover_image-clear": "on"})
    )
    assert response.status_code == 302
    event.refresh_from_db()
    assert not event.cover_image
    assert storage.exists(old_image)


def test_album_creation_upload_and_publication_use_same_gallery(client, content_editor):
    client.force_login(content_editor)
    response = client.post(
        reverse("panel:album_create"), {"title": "Retiro familiar", "event_date": "2028-11-15"}
    )
    assert response.status_code == 302
    album = Album.objects.get()
    assert response.url == reverse("panel:album_edit", args=[album.pk])
    assert client.get(reverse("gallery:detail", args=[album.slug])).status_code == 404
    Photo.objects.create(album=album, image=image_file(), alt_text="Foto existente", order=7)
    response = client.post(
        reverse("panel:album_upload", args=[album.pk]),
        {"images": [image_file("uno.png"), image_file("dos.png")], "alt_text": "Familias reunidas"},
    )
    assert response.status_code == 302
    assert list(album.photos.values_list("order", flat=True)) == [7, 8, 9]
    assert list(album.photos.filter(order__gte=8).values_list("alt_text", flat=True)) == [
        "Familias reunidas",
        "Familias reunidas",
    ]
    response = client.post(reverse("panel:album_action", args=[album.pk]), {"action": "publish"})
    assert response.status_code == 302
    public_page = client.get(reverse("gallery:detail", args=[album.slug]))
    assert public_page.status_code == 200
    assert "Familias reunidas" in public_page.content.decode()
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 3


def test_bulk_upload_validates_every_image_before_saving_any(client, content_editor):
    client.force_login(content_editor)
    album = Album.objects.create(title="Encuentro comunitario")
    response = client.post(
        reverse("panel:album_upload", args=[album.pk]),
        {"images": [image_file(), SimpleUploadedFile("falsa.png", b"texto privado")]},
    )
    assert response.status_code == 200
    assert response.context["upload_form"].errors
    assert not album.photos.exists()
    assert not LogEntry.objects.exclude(change_message__startswith="Inicio de sesión").exists()


def test_bulk_upload_rejects_more_than_thirty_files(client, content_editor):
    client.force_login(content_editor)
    album = Album.objects.create(title="Encuentro comunitario")
    response = client.post(
        reverse("panel:album_upload", args=[album.pk]),
        {"images": [image_file(f"foto-{index}.png") for index in range(31)]},
    )
    assert response.status_code == 200
    assert response.context["upload_form"].errors
    assert not album.photos.exists()


@pytest.mark.parametrize("route", ["photo_edit", "photo_delete"])
@pytest.mark.parametrize("method", ["get", "post"])
def test_photo_routes_cannot_access_another_albums_photo(client, content_editor, route, method):
    client.force_login(content_editor)
    album = Album.objects.create(title="Álbum correcto")
    other = Album.objects.create(title="Otro álbum")
    photo = Photo.objects.create(album=other, image=image_file(), alt_text="Foto original")
    response = getattr(client, method)(
        reverse(f"panel:{route}", args=[album.pk, photo.pk]),
        {"alt_text": "Intento de cambio", "order": 0},
    )
    assert response.status_code == 404
    photo.refresh_from_db()
    assert photo.alt_text == "Foto original"


def test_photo_metadata_edit_keeps_album_and_deletion_only_removes_database_record(
    client, content_editor
):
    client.force_login(content_editor)
    album = Album.objects.create(title="Encuentro comunitario")
    other = Album.objects.create(title="Álbum ajeno")
    photo = Photo.objects.create(album=album, image=image_file(), alt_text="Fotografía original")
    image_name = photo.image.name
    storage = photo.image.storage
    response = client.post(
        reverse("panel:photo_edit", args=[album.pk, photo.pk]),
        {
            "alt_text": "Familias orando",
            "caption": "Una tarde para compartir",
            "order": 3,
            "album": other.pk,
        },
    )
    assert response.status_code == 302
    photo.refresh_from_db()
    assert photo.album == album
    assert photo.alt_text == "Familias orando"
    assert photo.order == 3
    response = client.post(reverse("panel:photo_delete", args=[album.pk, photo.pk]))
    assert response.status_code == 302
    assert not Photo.objects.filter(pk=photo.pk).exists()
    assert storage.exists(image_name)


@pytest.mark.parametrize("section", ["event", "news", "album", "photo"])
def test_view_only_permission_renders_disabled_fields_and_blocks_post(
    client, permission_user, section
):
    viewer = permission_user("view_event", "view_post", "view_album", "view_photo")
    client.force_login(viewer)
    if section == "event":
        obj = make_event()
        route = reverse("panel:event_edit", args=[obj.pk])
        payload = event_data(title="Cambio no permitido")
    elif section == "news":
        obj = make_post(viewer)
        route = reverse("panel:news_edit", args=[obj.pk])
        payload = post_data(title="Cambio no permitido")
    elif section == "album":
        obj = Album.objects.create(title="Álbum original")
        route = reverse("panel:album_edit", args=[obj.pk])
        payload = {"title": "Cambio no permitido"}
    else:
        album = Album.objects.create(title="Álbum original")
        obj = Photo.objects.create(album=album, image=image_file(), alt_text="Foto original")
        route = reverse("panel:photo_edit", args=[album.pk, obj.pk])
        payload = {"alt_text": "Cambio no permitido", "order": 0}
    response = client.get(route)
    assert response.status_code == 200
    assert not response.context["can_save"]
    assert all(field.disabled for field in response.context["form"].fields.values())
    assert client.post(route, payload).status_code == 403
    obj.refresh_from_db()
    assert (obj.alt_text if section == "photo" else obj.title) != "Cambio no permitido"
    assert not LogEntry.objects.exclude(change_message__startswith="Inicio de sesión").exists()


@pytest.mark.parametrize("section", ["event", "news", "album"])
def test_content_actions_require_post_and_only_accept_known_actions(
    client, content_editor, section
):
    client.force_login(content_editor)
    obj = {
        "event": lambda: make_event(),
        "news": lambda: make_post(content_editor),
        "album": lambda: Album.objects.create(title="Galería de prueba"),
    }[section]()
    route = reverse(f"panel:{section}_action", args=[obj.pk])
    assert client.get(route, {"action": "publish"}).status_code == 405
    assert client.post(route, {"action": "delete_everything"}).status_code == 400
    obj.refresh_from_db()
    assert (obj.status == Post.Status.DRAFT) if section == "news" else not obj.is_published
    assert not LogEntry.objects.exclude(change_message__startswith="Inicio de sesión").exists()


def test_duplicate_event_requires_add_permission_too(client, permission_user):
    user = permission_user("view_event", "change_event")
    client.force_login(user)
    event = make_event()
    response = client.post(reverse("panel:event_action", args=[event.pk]), {"action": "duplicate"})
    assert response.status_code == 403
    assert Event.objects.count() == 1


@pytest.mark.parametrize("missing_permission", ["add_photo", "change_album", "view_album"])
def test_upload_requires_photo_add_and_album_access_and_change(
    client, permission_user, missing_permission
):
    permissions = {"add_photo", "change_album", "view_album"} - {missing_permission}
    user = permission_user(*permissions)
    client.force_login(user)
    album = Album.objects.create(title="Álbum protegido")
    response = client.post(
        reverse("panel:album_upload", args=[album.pk]), {"images": [image_file()]}
    )
    assert response.status_code == 403
    assert not album.photos.exists()


def test_album_delete_requires_permission_for_cascaded_photos(client, permission_user):
    user = permission_user("view_album", "delete_album")
    client.force_login(user)
    album = Album.objects.create(title="Álbum protegido")
    Photo.objects.create(album=album, image=image_file(), alt_text="Foto protegida")
    response = client.post(reverse("panel:album_delete", args=[album.pk]))
    assert response.status_code == 403
    assert Album.objects.filter(pk=album.pk).exists()
    assert album.photos.count() == 1


def test_content_search_filter_and_pagination_preserve_state(client, content_editor):
    client.force_login(content_editor)
    for index in range(14):
        make_event(title=f"Familias {index:02d}")
    make_event(title="Familias público", is_published=True)
    make_event(title="Actividad diferente")
    response = client.get(
        reverse("panel:event_list"), {"q": "Familias", "status": "draft", "pagina": 2}
    )
    assert response.status_code == 200
    assert response.context["page_obj"].paginator.count == 14
    assert len(response.context["page_obj"]) == 2
    assert "q=Familias" in response.context["pagination_query"]
    assert "status=draft" in response.context["pagination_query"]
    assert "pagina" not in response.context["pagination_query"]
    assert all(not obj.is_published for obj in response.context["page_obj"])


@pytest.mark.parametrize("section", ["event", "news", "album"])
def test_news_and_album_delete_require_confirmation_then_update_public_site(
    client, content_editor, section
):
    client.force_login(content_editor)
    if section == "event":
        obj = make_event(is_published=True)
        public_url = obj.get_absolute_url()
    elif section == "news":
        obj = make_post(content_editor, status=Post.Status.PUBLISHED)
        public_url = obj.get_absolute_url()
    else:
        obj = Album.objects.create(title="Álbum público", is_published=True)
        Photo.objects.create(album=obj, image=image_file(), alt_text="Foto de encuentro")
        public_url = reverse("gallery:detail", args=[obj.slug])
    route = reverse(f"panel:{section}_delete", args=[obj.pk])
    assert client.get(route).status_code == 200
    assert client.get(public_url).status_code == 200
    assert client.post(route).status_code == 302
    assert client.get(public_url).status_code == 404
