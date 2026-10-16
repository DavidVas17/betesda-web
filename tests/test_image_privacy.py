"""Las fotos se guardan sin ubicación GPS ni otros metadatos del teléfono."""

import io

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from PIL import Image

from apps.core.images import has_metadata, strip_metadata
from apps.gallery.models import Album, Photo

pytestmark = pytest.mark.django_db
GPS_IFD = 0x8825
ORIENTATION = 0x0112


def phone_photo(name="celular.jpg", orientation=1, fmt="JPEG"):
    """Una foto como la de un celular: con GPS, modelo del teléfono y orientación."""
    image = Image.new("RGB", (40, 20), "goldenrod")
    exif = image.getexif()
    exif[0x0110] = "Teléfono de prueba"  # modelo
    exif[ORIENTATION] = orientation
    exif.get_ifd(GPS_IFD).update({1: "N", 2: (14.0, 31.0, 12.0), 3: "W", 4: (90.0, 35.0, 1.0)})
    buffer = io.BytesIO()
    image.save(buffer, fmt, exif=exif.tobytes())
    return buffer.getvalue()


def opened(field):
    field.open("rb")
    return Image.open(field)


@pytest.fixture
def album():
    return Album.objects.create(title="Retiro")


def test_the_fixture_really_carries_gps():
    with Image.open(io.BytesIO(phone_photo())) as image:
        assert image.getexif().get_ifd(GPS_IFD)


def test_uploaded_photo_is_stored_without_metadata(album):
    photo = Photo.objects.create(
        album=album, image=SimpleUploadedFile("celular.jpg", phone_photo(), "image/jpeg")
    )

    with opened(photo.image) as stored:
        assert not stored.getexif()
        assert "exif" not in stored.info
        assert stored.format == "JPEG"
    assert photo.image.name.endswith(".jpg")


def test_orientation_is_applied_before_removing_it(album):
    # Orientación 6: el teléfono estaba de lado; la foto debe quedar vertical.
    photo = Photo.objects.create(
        album=album,
        image=SimpleUploadedFile("lado.jpg", phone_photo(orientation=6), "image/jpeg"),
    )

    with opened(photo.image) as stored:
        assert stored.size == (20, 40)


def test_png_and_webp_are_cleaned_too():
    for fmt in ("PNG", "WEBP"):
        clean = strip_metadata(ContentFile(phone_photo(fmt=fmt), name=f"x.{fmt.lower()}"))
        with Image.open(clean) as image:
            assert image.format == fmt
            assert not has_metadata(image)


def test_clean_images_are_left_alone():
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(buffer, "JPEG")

    assert strip_metadata(ContentFile(buffer.getvalue(), name="limpia.jpg")) is None


def test_panel_bulk_upload_strips_metadata(admin_client, album):
    admin_client.post(
        reverse("panel:album_upload", args=[album.pk]),
        {"images": [SimpleUploadedFile("a.jpg", phone_photo(), "image/jpeg")]},
    )

    photo = album.photos.get()
    with opened(photo.image) as stored:
        assert not stored.getexif()


def test_command_cleans_photos_uploaded_before(album, settings):
    photo = Photo.objects.create(
        album=album, image=SimpleUploadedFile("vieja.jpg", phone_photo(), "image/jpeg")
    )
    # Simula una foto subida antes de esta protección: se escribe con GPS directamente.
    storage = photo.image.storage
    storage.delete(photo.image.name)
    storage.save(photo.image.name, ContentFile(phone_photo()))
    with opened(photo.image) as before:
        assert before.getexif().get_ifd(GPS_IFD)

    call_command("strip_image_metadata")
    call_command("strip_image_metadata")  # la segunda vez no hay nada que limpiar

    photo.refresh_from_db()
    with opened(photo.image) as after:
        assert not after.getexif()
