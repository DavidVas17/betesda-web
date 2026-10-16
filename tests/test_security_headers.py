"""Cabeceras de seguridad en las respuestas."""

import re
from pathlib import Path

import pytest
from django.test import Client, override_settings

from apps.core.middleware import SecurityHeadersMiddleware

pytestmark = pytest.mark.django_db
TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def test_pages_send_a_strict_content_security_policy(client):
    policy = client.get("/").headers["Content-Security-Policy"]

    assert "default-src 'self'" in policy
    assert "script-src 'self'" in policy
    assert "unsafe-inline" not in policy
    assert "frame-ancestors 'none'" in policy
    assert "object-src 'none'" in policy


def test_browser_features_the_site_never_uses_are_disabled(client):
    header = client.get("/").headers["Permissions-Policy"]

    assert "camera=()" in header and "geolocation=()" in header


@override_settings(CSP_REPORT_ONLY=True)
def test_report_only_mode_does_not_block():
    response = Client().get("/")

    assert "Content-Security-Policy-Report-Only" in response.headers
    assert "Content-Security-Policy" not in response.headers


def test_middleware_keeps_a_policy_set_by_the_view(rf, settings):
    def view(request):
        from django.http import HttpResponse

        response = HttpResponse()
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response

    response = SecurityHeadersMiddleware(view)(rf.get("/"))

    assert response.headers["Content-Security-Policy"] == "default-src 'none'"


def test_templates_have_no_inline_code_that_the_policy_would_block():
    """Si alguien agrega un <script> o un style="" en línea, el navegador lo bloquearía."""
    offenders = []
    for path in TEMPLATES.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        for script in re.findall(r"<script\b[^>]*>", text):
            if "src=" not in script and "application/json" not in script:
                offenders.append(f"{path.name}: {script}")
        if re.search(r"\sstyle=\"|<style\b|\son[a-z]+=\"", text):
            offenders.append(f"{path.name}: estilo o evento en línea")
    assert offenders == []
