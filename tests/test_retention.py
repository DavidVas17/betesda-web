"""Plazo de conservación de mensajes y peticiones de oración."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.contacts.models import ContactMessage
from apps.contacts.retention import purge

pytestmark = pytest.mark.django_db
Status = ContactMessage.Status


@pytest.fixture(autouse=True)
def plazos(settings):
    settings.MESSAGE_RETENTION_DAYS = 365
    settings.SPAM_RETENTION_DAYS = 30
    settings.IP_RETENTION_DAYS = 90


def message(status, days_ago, ip="203.0.113.9"):
    item = ContactMessage.objects.create(
        name="Ana",
        email="ana@example.com",
        subject="Oración",
        message="…",
        status=status,
        source_ip=ip,
    )
    moment = timezone.now() - timedelta(days=days_ago)
    ContactMessage.objects.filter(pk=item.pk).update(created_at=moment, updated_at=moment)
    return item


def test_deletes_only_what_has_expired():
    old_closed = message(Status.CLOSED, 400)
    recent_closed = message(Status.CLOSED, 100)
    old_spam = message(Status.SPAM, 40)
    recent_spam = message(Status.SPAM, 5)

    result = purge()

    remaining = set(ContactMessage.objects.values_list("pk", flat=True))
    assert remaining == {recent_closed.pk, recent_spam.pk}
    assert (result.closed, result.spam) == (1, 1)
    assert not ContactMessage.objects.filter(pk__in=[old_closed.pk, old_spam.pk]).exists()


def test_open_requests_are_never_deleted_automatically():
    message(Status.NEW, 2000)
    message(Status.IN_PROGRESS, 2000)

    assert purge().deleted == 0
    assert ContactMessage.objects.count() == 2


def test_old_ips_are_forgotten_without_restarting_the_clock():
    item = message(Status.IN_PROGRESS, 120)
    before = ContactMessage.objects.get(pk=item.pk).updated_at

    assert purge().anonymized == 1

    item.refresh_from_db()
    assert item.source_ip is None
    assert item.updated_at == before


def test_dry_run_changes_nothing():
    message(Status.CLOSED, 400)
    out = StringIO()

    call_command("purge_old_messages", "--dry-run", stdout=out)

    assert "Se eliminarían: 1 cerrados" in out.getvalue()
    assert ContactMessage.objects.count() == 1


def test_command_deletes_and_reports():
    message(Status.CLOSED, 400)
    out = StringIO()

    call_command("purge_old_messages", stdout=out)

    assert "Eliminados: 1 cerrados" in out.getvalue()
    assert not ContactMessage.objects.exists()


def test_scheduled_deletion_date():
    assert message(Status.NEW, 1).scheduled_deletion is None
    closed = ContactMessage.objects.get(pk=message(Status.CLOSED, 10).pk)
    assert closed.scheduled_deletion == closed.updated_at + timedelta(days=365)


def test_contact_page_explains_the_retention(client):
    content = client.get(reverse("contacts:contact")).content.decode()

    assert "se elimina de forma automática después de 12 meses" in content


def test_team_sees_when_a_closed_request_will_be_deleted(admin_client):
    item = message(Status.CLOSED, 10)

    content = admin_client.get(reverse("panel:message_detail", args=[item.pk])).content.decode()

    assert "Se eliminará automáticamente el" in content
