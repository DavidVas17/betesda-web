import pytest
from django.core.exceptions import ValidationError

from apps.core.models import SiteConfiguration
from apps.events.models import Event


@pytest.mark.django_db
def test_site_configuration_is_singleton():
    SiteConfiguration.objects.create(institution_name="Betesda Rosa de Saron")
    second = SiteConfiguration(institution_name="Otra configuracion")

    with pytest.raises(ValidationError):
        second.full_clean()


@pytest.mark.django_db
def test_event_generates_slug():
    event = Event(
        title="Servicio de familia",
        summary="Reunion para todas las familias",
        description="Actividad de acompañamiento.",
        starts_at="2026-09-20T10:00:00Z",
        location="Templo principal",
    )
    event.save()

    assert event.slug == "servicio-de-familia"

