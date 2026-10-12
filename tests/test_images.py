"""Versiones WebP reducidas de las imágenes subidas."""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from PIL import Image

from apps.events.models import Event
from apps.gallery.models import Album, Photo

pytestmark = pytest.mark.django_db
User = get_user_model()


def jpeg(width=3000, height=2000, name="foto.jpg"):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "goldenrod").save(buffer, "JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def open_variant(field):
    field.open("rb")
    return Image.open(field)


def make_event(**extra):
    return Event.objects.create(
        title="Vigilia",
        summary="Oración",
        description="Detalles",
        starts_at=timezone.now(),
        location="Templo",
        **extra,
    )


def test_uploading_a_cover_creates_reduced_webp_versions():
    event = make_event(cover_image=jpeg())

    card = open_variant(event.cover_card)
    large = open_variant(event.cover_large)
    assert card.format == "WEBP" and card.width == 960
    assert large.format == "WEBP" and large.width == 1600
    assert event.card_image_url.endswith(".webp")
    assert event.cover_image.name.endswith(".jpg")


def test_small_images_are_not_enlarged():
    event = make_event(cover_image=jpeg(600, 400))

    assert open_variant(event.cover_card).width == 600


def test_replacing_and_clearing_the_cover_updates_its_versions():
    event = make_event(cover_image=jpeg(name="primera.jpg"))
    first = event.cover_card.name

    event.cover_image = jpeg(name="segunda.jpg")
    event.save()
    assert event.cover_card.name != first
    assert "segunda" in event.cover_card.name

    event.cover_image = None
    event.save()
    event.refresh_from_db()
    assert not event.cover_card
    assert event.card_image_url == ""


def test_saving_other_fields_does_not_regenerate_versions():
    event = make_event(cover_image=jpeg())
    name = event.cover_card.name

    event.refresh_from_db()
    event.title = "Nuevo título"
    event.save()

    assert event.cover_card.name == name


def test_gallery_photos_get_thumbnail_and_display_versions():
    album = Album.objects.create(title="Retiro")
    photo = Photo.objects.create(album=album, image=jpeg(), alt_text="Foto")

    assert open_variant(photo.thumb).width == 800
    assert open_variant(photo.display).width == 1800
    assert photo.thumb_url != photo.image.url


def test_command_creates_versions_for_existing_images():
    event = make_event(cover_image=jpeg())
    Event.objects.filter(pk=event.pk).update(cover_card="", cover_large="")

    call_command("generate_image_variants")

    event.refresh_from_db()
    assert event.cover_card and event.cover_large


def test_unreadable_image_keeps_the_original_without_failing():
    album = Album.objects.create(title="Retiro")
    photo = Photo(album=album, alt_text="Foto")
    photo.image.save("rota.jpg", SimpleUploadedFile("rota.jpg", b"no es una imagen"), save=False)
    photo.save()

    assert not photo.thumb
    assert photo.thumb_url == photo.image.url
