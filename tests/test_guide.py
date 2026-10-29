"""Guía rápida y primeros pasos del panel."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts import totp, two_factor
from apps.accounts.roles import CARE, CHURCH_ADMIN, set_user_roles

pytestmark = pytest.mark.django_db
User = get_user_model()


def member(role, **extra):
    user = User.objects.create_user("ana", password="clave-larga-2026", is_staff=True, **extra)
    set_user_roles(user, [role.name])
    return user


def test_guide_shows_only_what_the_role_can_do(client):
    client.force_login(member(CARE))

    content = client.get(reverse("panel:guide")).content.decode()

    assert "Atender una petición" in content
    assert "Tu cuenta y tu seguridad" in content
    assert "Publicar un evento" not in content
    assert "Agregar a alguien al equipo" not in content


def test_church_admin_sees_every_topic(client):
    client.force_login(member(CHURCH_ADMIN))

    content = client.get(reverse("panel:guide")).content.decode()

    for title in ("Publicar un evento", "Subir fotos", "Agregar a alguien al equipo"):
        assert title in content


def test_guide_is_linked_from_the_sidebar(client):
    client.force_login(member(CARE))

    assert reverse("panel:guide") in client.get(reverse("panel:dashboard")).content.decode()


def test_first_steps_until_the_account_is_ready(client):
    user = member(CARE)
    client.force_login(user)
    assert "Tus primeros pasos" in client.get(reverse("panel:dashboard")).content.decode()

    user.first_name, user.email = "Ana", "ana@example.com"
    user.save()
    device = two_factor.start_setup(user)
    two_factor.confirm_setup(user, totp.code_at(device.secret, totp.current_step()))

    assert "Tus primeros pasos" not in client.get(reverse("panel:dashboard")).content.decode()
