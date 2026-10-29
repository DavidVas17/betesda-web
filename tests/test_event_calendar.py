"""Agregar eventos al calendario y compartirlos."""

from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse

from apps.events import calendar
from apps.events.models import Event

pytestmark = pytest.mark.django_db
GT = ZoneInfo("America/Guatemala")


@pytest.fixture
def vigil():
    return Event.objects.create(
        title="Vigilia de oración, adoración; y alabanza",
        summary="Una noche para orar juntos",
        description="Detalles",
        starts_at=datetime(2026, 11, 20, 19, 0, tzinfo=GT),
        location="Templo principal, Villa Nueva",
        is_published=True,
    )


def test_ics_file_is_valid_and_in_utc(client, vigil):
    response = client.get(reverse("events:ics", args=[vigil.slug]))

    assert response["Content-Type"].startswith("text/calendar")
    assert f'filename="{vigil.slug}.ics"' in response["Content-Disposition"]
    text = response.content.decode()
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
    assert "DTSTART:20261121T010000Z" in text  # 19:00 en Guatemala = 01:00 UTC
    assert "DTEND:20261121T030000Z" in text  # sin hora de fin: 2 horas
    assert "SUMMARY:Vigilia de oración\\, adoración\\; y alabanza" in text
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))


def test_unpublished_events_have_no_calendar_file(client, vigil):
    vigil.is_published = False
    vigil.save()

    assert client.get(reverse("events:ics", args=[vigil.slug])).status_code == 404


def test_google_calendar_link(vigil):
    url = calendar.google_calendar_url(vigil, "https://iglesia.example/e/")
    query = parse_qs(urlsplit(url).query)

    assert query["dates"] == ["20261121T010000Z/20261121T030000Z"]
    assert query["ctz"] == ["America/Guatemala"]


def test_share_text_has_date_place_and_link(vigil):
    text = calendar.share_text(vigil, "https://iglesia.example/e/")

    assert "viernes 20 de noviembre, 19:00 h" in text
    assert "Templo principal" in text and text.endswith("https://iglesia.example/e/")


def test_detail_page_offers_calendar_and_sharing(client, vigil):
    vigil.starts_at = vigil.starts_at.replace(year=2030)
    vigil.ends_at = vigil.starts_at + timedelta(hours=3)
    vigil.save()

    content = client.get(vigil.get_absolute_url()).content.decode()

    assert reverse("events:ics", args=[vigil.slug]) in content
    assert "calendar.google.com" in content
    assert "https://wa.me/?text=" in content
    assert "facebook.com/sharer" in content
