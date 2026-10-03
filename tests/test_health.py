import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_liveness_endpoint(client):
    response = client.get(reverse("core:health-live"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "betesda-web"}


@pytest.mark.django_db
def test_readiness_endpoint_checks_database(client):
    response = client.get(reverse("core:health-ready"))

    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_home_page_is_accessible(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert "Betesda Rosa de Sarón" in response.content.decode()

