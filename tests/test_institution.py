"""Ministerios, valores y textos institucionales editables desde el panel."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.roles import CHURCH_ADMIN, COORDINATOR, set_user_roles
from apps.core.models import ChurchValue, Ministry, SiteConfiguration

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def church_admin(client):
    user = User.objects.create_user(username="pastor", is_staff=True)
    set_user_roles(user, [CHURCH_ADMIN.name])
    client.force_login(user)
    return user


def test_initial_content_is_loaded_by_the_migration():
    assert list(Ministry.objects.values_list("slug", flat=True)[:3]) == [
        "infantil",
        "jovenes",
        "adultos",
    ]
    assert ChurchValue.objects.count() == 10


def test_church_admin_lists_and_edits_a_ministry(client, church_admin):
    ministry = Ministry.objects.get(slug="jovenes")

    overview = client.get(reverse("panel:institution")).content.decode()
    response = client.post(
        reverse("panel:institution_edit", args=["ministerios", ministry.pk]),
        {
            "name": "Ministerio Juvenil",
            "tag": "Jóvenes",
            "icon": "sparkles",
            "description": "Nueva descripción.",
            "order": 5,
            "is_active": "on",
        },
    )

    assert "Ministerio de Jóvenes" in overview
    assert response.status_code == 302
    ministry.refresh_from_db()
    assert ministry.name == "Ministerio Juvenil"
    assert ministry.slug == "jovenes"
    page = client.get(reverse("core:ministries")).content.decode()
    assert "Ministerio Juvenil" in page


def test_church_admin_creates_and_deletes_a_value(client, church_admin):
    client.post(
        reverse("panel:institution_create", args=["valores"]),
        {"name": "Gratitud", "description": "Agradecemos cada día.", "order": 1, "is_active": "on"},
    )
    value = ChurchValue.objects.get(name="Gratitud")

    client.post(reverse("panel:institution_delete", args=["valores", value.pk]))

    assert not ChurchValue.objects.filter(pk=value.pk).exists()


def test_unknown_section_returns_404(client, church_admin):
    assert client.get(reverse("panel:institution_create", args=["otra"])).status_code == 404


def test_coordinator_cannot_edit_institutional_content(client):
    user = User.objects.create_user(username="coordina", is_staff=True)
    set_user_roles(user, [COORDINATOR.name])
    client.force_login(user)
    ministry = Ministry.objects.first()

    assert client.get(reverse("panel:institution")).status_code == 403
    url = reverse("panel:institution_edit", args=["ministerios", ministry.pk])
    assert client.post(url, {"name": "X"}).status_code == 403


def test_settings_edit_the_mission_shown_on_the_site(client, church_admin):
    response = client.post(
        reverse("panel:settings"),
        {
            "institution_name": "Betesda",
            "mission": "Misión editada desde el panel.",
            "vision": "",
            "purpose": "",
            "history": "",
        },
    )

    assert response.status_code == 302
    assert SiteConfiguration.objects.get().mission == "Misión editada desde el panel."
    assert "Misión editada desde el panel." in client.get(reverse("core:about")).content.decode()
