"""La sesión del panel caduca por inactividad."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db
User = get_user_model()


def test_session_lasts_hours_not_weeks(settings):
    assert settings.SESSION_COOKIE_AGE <= 12 * 3600
    assert settings.SESSION_SAVE_EVERY_REQUEST is True


def test_each_visit_renews_the_session(client):
    user = User.objects.create_user(username="ana", password="clave-larga-2026", is_staff=True)
    client.force_login(user)

    response = client.get(reverse("panel:dashboard"))

    cookie = response.cookies["sessionid"]
    assert int(cookie["max-age"]) > 0


def test_anonymous_visitors_do_not_get_a_session(client):
    response = client.get("/")

    assert "sessionid" not in response.cookies


def test_expired_session_explains_why_on_login(client):
    response = client.get(reverse("panel:event_list"), follow=True)

    content = response.content.decode()
    assert "continuar donde te quedaste" in content
    assert 'name="next"' in content
