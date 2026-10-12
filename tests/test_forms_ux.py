"""Presentación de los formularios: bloques, resumen de errores y mejoras progresivas."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.roles import COLLABORATOR, set_user_roles

pytestmark = pytest.mark.django_db
User = get_user_model()


def test_event_form_is_grouped_in_numbered_blocks(admin_client):
    content = admin_client.get(reverse("panel:event_create")).content.decode()

    for title in ("Lo básico", "Fecha y lugar", "Detalles", "Imagen", "Publicación"):
        assert title in content
    assert "data-enhanced-form" in content
    assert "data-dirty-guard" in content
    assert "js/forms.js" in content
    assert 'class="p-switch"' in content
    assert "data-starts" in content and "data-ends" in content


def test_collaborator_form_skips_the_publication_block(client):
    user = User.objects.create_user(username="colabora", is_staff=True)
    set_user_roles(user, [COLLABORATOR.name])
    client.force_login(user)

    content = client.get(reverse("panel:event_create")).content.decode()

    assert "Lo básico" in content
    assert "Publicación" not in content


def test_news_status_is_offered_as_described_choices(admin_client):
    content = admin_client.get(reverse("panel:news_create")).content.decode()

    assert 'type="radio" name="status"' in content
    assert "Solo el equipo la ve." in content


def test_server_errors_are_summarized_with_links_to_each_field(admin_client):
    response = admin_client.post(reverse("panel:event_create"), {"title": ""})

    content = response.content.decode()
    assert response.status_code == 200
    assert "fk-summary" in content
    assert 'href="#id_title"' in content
    assert 'href="#id_location"' in content


def test_contact_form_is_enhanced_and_summarizes_errors(client):
    page = client.get(reverse("contacts:contact")).content.decode()
    assert "data-enhanced-form" in page
    assert "js/forms.js" in page

    response = client.post(reverse("contacts:send"), {"kind": "PRAYER"}, follow=True)
    content = response.content.decode()
    assert "fk-summary" in content
    assert 'href="#id_name"' in content


def test_login_form_shows_loading_state_label(client):
    content = client.get(reverse("panel:login")).content.decode()

    assert 'data-loading-label="Ingresando…"' in content
    assert "data-no-counter" in content
