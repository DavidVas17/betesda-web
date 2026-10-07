from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.contacts.models import ContactMessage
from apps.core.content import MINISTRIES, VALUES
from apps.core.models import SiteConfiguration
from apps.events.models import Event
from apps.gallery.models import Album, Photo
from apps.news.models import Post

pytestmark = pytest.mark.django_db


def make_event(**overrides):
    data = {
        "title": "Actividad de familias",
        "summary": "Compartamos juntos",
        "description": "Alabanza y enseñanza.",
        "starts_at": timezone.now() + timedelta(days=2),
        "location": "Templo principal",
        "is_published": True,
    }
    data.update(overrides)
    return Event.objects.create(**data)


@pytest.mark.parametrize(
    "route",
    [
        "core:home",
        "core:about",
        "core:ministries",
        "events:list",
        "news:list",
        "gallery:list",
        "contacts:contact",
    ],
)
def test_public_pages_have_full_navigation_and_active_link(client, route):
    response = client.get(reverse(route))
    content = response.content.decode()
    assert response.status_code == 200
    for destination in (
        "core:home",
        "core:about",
        "core:ministries",
        "events:list",
        "news:list",
        "gallery:list",
        "contacts:contact",
    ):
        assert f'href="{reverse(destination)}"' in content
    assert f'href="{reverse(route)}" aria-current="page"' in content
    assert "css/site.css" in content
    assert "logo-betesda.jpg" in content


def test_home_has_limited_previews_and_contact_link_instead_of_form(client):
    events = [make_event(title=f"Actividad {index}") for index in range(5)]
    response = client.get(reverse("core:home"))
    assert list(response.context["events"]) == events[:3]
    assert 'class="contact-form"' not in response.content.decode()
    assert "Nuestra misión" in response.content.decode()
    assert "Desde 2006" in response.content.decode()
    assert "Noticias y anuncios" in response.content.decode()
    assert "Pronto compartiremos nuevas noticias" in response.content.decode()
    assert f'href="{reverse("news:list")}"' in response.content.decode()


def test_home_limits_news_preview_and_prioritizes_featured_posts(client, admin_user):
    posts = [
        Post.objects.create(
            title=f"Noticia {index}",
            excerpt="Resumen de la noticia",
            body="Contenido",
            author=admin_user,
            status=Post.Status.PUBLISHED,
            published_at=timezone.now() - timedelta(days=index + 1),
            is_featured=index == 4,
        )
        for index in range(5)
    ]

    response = client.get(reverse("core:home"))

    assert list(response.context["posts"]) == [posts[4], posts[0], posts[1]]
    content = response.content.decode()
    for post in (posts[4], posts[0], posts[1]):
        assert post.title in content
        assert f'href="{post.get_absolute_url()}"' in content
    for post in (posts[2], posts[3]):
        assert post.title not in content
    assert "Pronto compartiremos nuevas noticias" not in content


def test_institutional_pages_use_provided_information(client):
    content = client.get(reverse("core:about")).content.decode()
    for heading in ("Misión", "Visión", "Propósito", "2006"):
        assert heading in content
    for name, _ in VALUES:
        assert name in content
    content = client.get(reverse("core:ministries")).content.decode()
    for ministry in MINISTRIES:
        assert ministry["name"] in content


def test_contact_details_follow_backoffice_configuration(client):
    SiteConfiguration.objects.create(
        institution_name="Betesda",
        address="Dirección actualizada",
        phone="5555-1234",
        email="iglesia@example.com",
        facebook_url="https://www.facebook.com/betesda",
        map_url="https://www.google.com/maps/place/Betesda",
    )
    content = client.get(reverse("contacts:contact")).content.decode()
    assert "Dirección actualizada" in content
    assert 'href="tel:+50255551234"' in content
    assert 'href="mailto:iglesia@example.com"' in content
    assert "https://www.facebook.com/betesda" in content


def test_contact_map_follows_configured_address_and_preserves_directions_link(client):
    configuration = SiteConfiguration.objects.create(
        institution_name="Betesda",
        address="13 calle 13-02, Santa Isabel II, Villa Nueva",
        map_url="https://www.google.com/maps/place/Betesda",
    )
    response = client.get(reverse("contacts:contact"))
    embed = urlsplit(response.context["site"]["map_embed_url"])
    query = parse_qs(embed.query)
    assert embed.scheme == "https"
    assert embed.netloc == "www.google.com"
    assert query["q"] == [f"{configuration.address} Guatemala"]
    assert query["output"] == ["embed"]
    assert response.context["site"]["map_url"] == configuration.map_url
    assert '<iframe src="https://www.google.com/maps?' in response.content.decode()

    configuration.address = "Otra dirección & sector 2, Villa Nueva"
    configuration.save()
    response = client.get(reverse("contacts:contact"))
    query = parse_qs(urlsplit(response.context["site"]["map_embed_url"]).query)
    assert query["q"] == [f"{configuration.address} Guatemala"]


def test_events_hide_drafts_and_separate_past_from_upcoming(client):
    future = make_event(title="Actividad próxima")
    ongoing = make_event(
        title="Actividad en curso",
        starts_at=timezone.now() - timedelta(hours=1),
        ends_at=timezone.now() + timedelta(hours=1),
    )
    past = make_event(title="Actividad anterior", starts_at=timezone.now() - timedelta(days=2))
    draft = make_event(title="Borrador reservado", is_published=False)
    response = client.get(reverse("events:list"))
    assert set(response.context["page_obj"]) == {future, ongoing}
    assert past.title not in response.content.decode()
    assert draft.title not in response.content.decode()
    response = client.get(reverse("events:list"), {"vista": "anteriores"})
    assert list(response.context["page_obj"]) == [past]
    assert client.get(draft.get_absolute_url()).status_code == 404
    assert client.get(future.get_absolute_url()).status_code == 200


def test_events_pagination_preserves_previous_activity_filter(client):
    for index in range(10):
        make_event(title=f"Actividad {index}", starts_at=timezone.now() - timedelta(days=index + 1))
    response = client.get(reverse("events:list"), {"vista": "anteriores"})
    assert len(response.context["page_obj"]) == 9
    assert "pagina=2&amp;vista=anteriores" in response.content.decode()
    response = client.get(reverse("events:list"), {"vista": "anteriores", "pagina": 2})
    assert len(response.context["page_obj"]) == 1


def test_news_only_shows_published_past_dates(client, admin_user):
    published = Post.objects.create(
        title="Anuncio público",
        excerpt="Información",
        body="Texto del anuncio",
        author=admin_user,
        status=Post.Status.PUBLISHED,
    )
    draft = Post.objects.create(
        title="Anuncio reservado", excerpt="Borrador", body="Privado", author=admin_user
    )
    scheduled = Post.objects.create(
        title="Anuncio futuro",
        excerpt="Programado",
        body="Futuro",
        author=admin_user,
        status=Post.Status.PUBLISHED,
        published_at=timezone.now() + timedelta(days=2),
    )
    archived = Post.objects.create(
        title="Anuncio archivado",
        excerpt="Archivo",
        body="Anterior",
        author=admin_user,
        status=Post.Status.ARCHIVED,
    )
    for route in ("news:list", "core:home"):
        content = client.get(reverse(route)).content.decode()
        assert published.title in content
        for hidden in (draft, scheduled, archived):
            assert hidden.title not in content
    assert client.get(published.get_absolute_url()).status_code == 200
    for hidden in (draft, scheduled, archived):
        assert client.get(hidden.get_absolute_url()).status_code == 404


def test_gallery_shows_published_albums_and_photo_metadata(client):
    album = Album.objects.create(title="Encuentro comunitario", is_published=True)
    draft = Album.objects.create(title="Álbum reservado")
    photo = Photo.objects.create(
        album=album,
        image=SimpleUploadedFile("foto.jpg", b"fake-image", content_type="image/jpeg"),
        alt_text="Comunidad reunida",
        caption="Un día para compartir",
    )
    content = client.get(reverse("gallery:list")).content.decode()
    assert album.title in content
    assert draft.title not in content
    assert photo.alt_text in content
    response = client.get(reverse("gallery:detail", args=[album.slug]))
    assert response.status_code == 200
    assert photo.caption in response.content.decode()
    assert "data-gallery-photo" in response.content.decode()
    assert client.get(reverse("gallery:detail", args=[draft.slug])).status_code == 404


def test_contact_message_data_is_never_exposed_on_public_pages(client):
    ContactMessage.objects.create(
        name="Nombre reservado",
        email="privado@example.com",
        subject="Petición reservada",
        message="Texto privado",
        privacy_accepted=True,
        kind=ContactMessage.Kind.PRAYER,
    )
    for route in ("core:home", "contacts:contact", "news:list", "gallery:list"):
        content = client.get(reverse(route)).content.decode()
        for value in (
            "Nombre reservado",
            "privado@example.com",
            "Petición reservada",
            "Texto privado",
        ):
            assert value not in content


@pytest.mark.parametrize("route", ["events:detail", "news:detail", "gallery:detail"])
def test_unknown_public_details_return_404(client, route):
    assert client.get(reverse(route, args=["no-existe"])).status_code == 404
