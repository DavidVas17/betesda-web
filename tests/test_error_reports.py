"""Los reportes de error por correo no llevan datos privados."""

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db
PRIVATE = "Oren por mi diagnóstico de cáncer"


def test_contact_crash_report_hides_the_prayer(settings, monkeypatch):
    settings.ADMINS = [("Soporte", "soporte@example.com")]

    def boom(**kwargs):
        raise RuntimeError("falla de prueba")

    monkeypatch.setattr("apps.contacts.views.spam_reasons", boom)
    client = Client(raise_request_exception=False)

    response = client.post(
        reverse("contacts:send"),
        {
            "kind": "PRAYER",
            "name": "Ana Pérez",
            "email": "ana@example.com",
            "subject": "Salud",
            "message": PRIVATE,
            "privacy_accepted": "on",
        },
    )

    assert response.status_code == 500
    report = next(m for m in mail.outbox if "soporte@example.com" in m.to)
    assert "RuntimeError" in report.body
    for private in (PRIVATE, "Ana Pérez", "ana@example.com"):
        assert private not in report.body
