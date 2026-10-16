"""Horarios de culto: cálculo del próximo culto, sitio público y panel."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.roles import CHURCH_ADMIN, set_user_roles
from apps.core.models import ServiceTime
from apps.core.schedule import by_day, next_service

pytestmark = pytest.mark.django_db
User = get_user_model()
GT = ZoneInfo("America/Guatemala")
Day = ServiceTime.Day


def service(name, day, start, end=None, **extra):
    return ServiceTime.objects.create(
        name=name, day=day, starts_at=time(*start), ends_at=time(*end) if end else None, **extra
    )


@pytest.fixture
def week():
    return [
        service("Culto general", Day.SUNDAY, (10, 0), (12, 0)),
        service("Oración", Day.WEDNESDAY, (19, 0), (20, 30)),
        service("Jóvenes", Day.SATURDAY, (17, 0)),
    ]


def at(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=GT)


def test_next_service_later_today(week):
    # Miércoles 14 de octubre de 2026, 18:00
    result = next_service(week, at(2026, 10, 14, 18))

    assert result.service.name == "Oración"
    assert result.label == "Hoy"
    assert not result.in_progress


def test_service_in_progress_is_shown_as_now(week):
    result = next_service(week, at(2026, 10, 14, 19, 30))

    assert result.service.name == "Oración"
    assert result.label == "Ahora"
    assert result.in_progress


def test_after_a_service_ends_the_next_one_is_chosen(week):
    result = next_service(week, at(2026, 10, 14, 21))

    assert result.service.name == "Jóvenes"
    assert result.label == "Sábado"


def test_tomorrow_label(week):
    result = next_service(week, at(2026, 10, 16, 20))  # viernes

    assert result.service.name == "Jóvenes"
    assert result.label == "Mañana"


def test_week_wraps_to_next_sunday(week):
    result = next_service(week, at(2026, 10, 18, 13))  # domingo, después del culto

    assert result.service.name == "Oración"
    assert result.starts.day == 21


def test_service_without_end_time_counts_two_hours(week):
    result = next_service(week, at(2026, 10, 17, 18, 30))  # sábado 18:30

    assert result.service.name == "Jóvenes"
    assert result.in_progress


def test_no_services_means_no_next_service():
    assert next_service([], at(2026, 10, 14, 18)) is None


def test_services_are_grouped_by_day_in_week_order(week):
    days = [name for name, _ in by_day(week)]

    assert days == ["Miércoles", "Sábado", "Domingo"]


def test_end_time_must_follow_start_time():
    item = ServiceTime(name="X", day=Day.MONDAY, starts_at=time(19), ends_at=time(18))

    with pytest.raises(Exception, match="después del inicio"):
        item.full_clean()


def test_home_and_contact_show_active_schedules(client, week):
    service("Culto suspendido", Day.FRIDAY, (19, 0), is_active=False)

    home = client.get(reverse("core:home")).content.decode()
    contact = client.get(reverse("contacts:contact")).content.decode()

    assert "Horarios de culto" in home
    assert "Culto general" in home and "10:00 a 12:00 h" in home
    assert "Próximo culto" in home or "En este momento" in home
    assert "Culto suspendido" not in home
    assert "Horarios de culto" in contact and "Oración" in contact


def test_schedule_section_is_hidden_until_there_are_schedules(client):
    assert "Horarios de culto" not in client.get(reverse("core:home")).content.decode()


def test_church_admin_adds_a_service_from_the_panel(client):
    user = User.objects.create_user(username="pastora", is_staff=True)
    set_user_roles(user, [CHURCH_ADMIN.name])
    client.force_login(user)

    page = client.get(reverse("panel:institution")).content.decode()
    response = client.post(
        reverse("panel:institution_create", args=["horarios"]),
        {
            "name": "Culto de oración",
            "note": "Para toda la familia",
            "day": Day.THURSDAY,
            "starts_at": "19:00",
            "ends_at": "20:30",
            "is_active": "on",
        },
    )

    assert "Horarios de culto" in page
    assert response.status_code == 302
    created = ServiceTime.objects.get(name="Culto de oración")
    assert created.time_label == "19:00 a 20:30"


def test_panel_rejects_an_end_time_before_the_start(client):
    user = User.objects.create_user(username="pastor-horario", is_staff=True)
    set_user_roles(user, [CHURCH_ADMIN.name])
    client.force_login(user)

    response = client.post(
        reverse("panel:institution_create", args=["horarios"]),
        {"name": "Mal horario", "day": Day.MONDAY, "starts_at": "19:00", "ends_at": "18:00"},
    )

    assert response.status_code == 200
    assert not ServiceTime.objects.exists()
