"""Comando que crea o actualiza al superadministrador desde variables de entorno."""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "jefe")
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "jefe@example.com")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "una-clave-larga-2026")
    return monkeypatch


def test_creates_the_superuser(admin_env):
    call_command("bootstrap_admin")

    user = User.objects.get(username="jefe")
    assert user.is_superuser and user.is_staff and user.is_active
    assert user.check_password("una-clave-larga-2026")


def test_updating_keeps_the_current_password(admin_env):
    """Correrlo para cambiar el correo no debe cambiar la contraseña sin avisar."""
    User.objects.create_user(username="jefe", password="mi-clave-actual-26", is_active=False)
    admin_env.setenv("DJANGO_SUPERUSER_EMAIL", "nuevo@example.com")

    call_command("bootstrap_admin")

    user = User.objects.get(username="jefe")
    assert user.email == "nuevo@example.com"
    assert user.is_superuser and user.is_active
    assert user.check_password("mi-clave-actual-26")
    assert User.objects.filter(username="jefe").count() == 1


def test_reset_password_flag_replaces_it(admin_env):
    User.objects.create_user(username="jefe", password="mi-clave-actual-26")
    admin_env.setenv("DJANGO_SUPERUSER_PASSWORD", "otra-clave-larga-2026")

    call_command("bootstrap_admin", "--reset-password")

    assert User.objects.get(username="jefe").check_password("otra-clave-larga-2026")


def test_requires_all_variables(admin_env):
    admin_env.delenv("DJANGO_SUPERUSER_EMAIL")

    with pytest.raises(CommandError):
        call_command("bootstrap_admin")
    assert not User.objects.exists()


def test_rejects_the_example_password(admin_env):
    admin_env.setenv("DJANGO_SUPERUSER_PASSWORD", "replace-me-before-use")

    with pytest.raises(CommandError):
        call_command("bootstrap_admin")


@pytest.mark.parametrize("weak", ["corta12", "1234567890", "password123"])
def test_rejects_weak_passwords(admin_env, weak):
    admin_env.setenv("DJANGO_SUPERUSER_PASSWORD", weak)

    with pytest.raises(CommandError, match="no es segura"):
        call_command("bootstrap_admin")
    assert not User.objects.exists()


def test_weak_env_password_does_not_block_updating_email(admin_env):
    User.objects.create_user(username="jefe", password="mi-clave-actual-26")
    admin_env.setenv("DJANGO_SUPERUSER_PASSWORD", "corta")

    call_command("bootstrap_admin")

    assert User.objects.get(username="jefe").check_password("mi-clave-actual-26")
