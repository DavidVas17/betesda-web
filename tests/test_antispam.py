"""Defensas del formulario de contacto contra bots y spam."""

import io
import json
import re
import time

import pytest
from django.core import signing
from django.urls import reverse

from apps.contacts import spam, turnstile
from apps.contacts.models import ContactMessage

pytestmark = pytest.mark.django_db
SEND = reverse("contacts:send")


def data(**extra):
    values = {
        "kind": "PRAYER",
        "name": "Ana Pérez",
        "email": "ana@example.com",
        "subject": "Salud de mi familia",
        "message": "Por favor oren por la salud de mi mamá.",
        "privacy_accepted": "on",
    }
    values.update(extra)
    return values


def started_ago(seconds):
    return signing.dumps(time.time() - seconds, salt="contacts.formulario")


@pytest.fixture
def time_trap(settings):
    settings.CONTACT_TIME_TRAP = (3, 7200)


# --- Trampa de tiempo -----------------------------------------------------------------------------


def test_form_carries_a_signed_timestamp(client, time_trap):
    page = client.get(reverse("contacts:contact")).content.decode()

    token = re.search(r'name="started" value="([^"]+)"', page).group(1)
    assert spam.time_trap_verdict(token) == "enviado demasiado rápido"


def test_person_taking_a_few_seconds_gets_through(client, time_trap):
    response = client.post(SEND, data(started=started_ago(8)))

    assert response.status_code == 302
    assert ContactMessage.objects.count() == 1


# Cada marca se crea al correr la prueba, no al cargar el archivo: si se creara antes, en una
# máquina lenta ya habrían pasado los 3 segundos y el "bot" parecería una persona.
BOT_TOKENS = {
    "demasiado-rapido": lambda: started_ago(1),
    "sin-marca": lambda: "",
    "manipulada": lambda: "manipulado",
    "firma-de-otro-formulario": lambda: signing.dumps(time.time(), salt="otra-cosa"),
}


@pytest.mark.parametrize("case", BOT_TOKENS)
def test_bots_are_silently_discarded(client, time_trap, case):
    response = client.post(SEND, data(started=BOT_TOKENS[case]()), follow=True)

    assert "Recibimos tu petición" in response.content.decode() or response.status_code == 200
    assert not ContactMessage.objects.exists()


def test_slow_people_are_not_punished(client, settings):
    settings.CONTACT_TIME_TRAP = (3, 10)

    client.post(SEND, data(started=started_ago(60)))

    assert ContactMessage.objects.count() == 1


# --- Contenido ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"message": "Visit https://a.example https://b.example https://c.example now"},
        {"name": "Cheap www.pills.example"},
        {"message": "Best crypto investment opportunity, write me on telegram"},
        {"message": "Продвижение сайтов и рекламные услуги недорого для вашего бизнеса"},
    ],
)
def test_spam_is_kept_aside_without_notifying(
    client, fields, mailoutbox, django_capture_on_commit_callbacks, settings
):
    settings.CONTACT_NOTIFY_EMAILS = ["iglesia@example.com"]

    with django_capture_on_commit_callbacks(execute=True):
        client.post(SEND, data(**fields))

    message = ContactMessage.objects.get()
    assert message.status == ContactMessage.Status.SPAM
    assert "automáticamente" in message.internal_notes
    assert mailoutbox == []


def test_normal_prayer_with_one_link_is_fine():
    assert (
        spam.spam_reasons(
            name="Ana Pérez",
            subject="Oración",
            message="Oren por mi hermano, aquí está su historia https://ejemplo.org/hermano",
        )
        == []
    )


def test_spanish_accents_are_not_foreign_script():
    assert spam.spam_reasons(name="Ñandú Pérez", subject="Peña", message="Oración, señor.") == []


# --- Repeticiones -------------------------------------------------------------------------------


def test_same_message_twice_is_saved_once(client):
    client.post(SEND, data())
    response = client.post(SEND, data(message="  POR favor oren por la salud   de mi mamá. "))

    assert response.status_code == 302
    assert ContactMessage.objects.count() == 1


def test_one_email_cannot_flood(client, settings):
    settings.CONTACT_EMAIL_RATE_LIMIT = (2, 3600)
    for number in range(2):
        client.post(SEND, data(message=f"Mensaje {number}"), REMOTE_ADDR=f"192.0.2.{number}")

    response = client.post(SEND, data(message="Otro más"), REMOTE_ADDR="192.0.2.9")

    assert response.status_code == 429
    assert ContactMessage.objects.count() == 2


# --- Turnstile ----------------------------------------------------------------------------------


@pytest.fixture
def turnstile_keys(settings):
    settings.TURNSTILE_SITE_KEY = "clave-publica"
    settings.TURNSTILE_SECRET_KEY = "clave-secreta"


def fake_cloudflare(monkeypatch, *, success=True, fail=False):
    calls = []

    def urlopen(request, timeout):
        calls.append(request.data.decode())
        if fail:
            raise OSError("sin red")
        return io.BytesIO(json.dumps({"success": success}).encode())

    monkeypatch.setattr(turnstile.urllib.request, "urlopen", urlopen)
    return calls


def test_without_keys_there_is_no_widget(client):
    assert "cf-turnstile" not in client.get(reverse("contacts:contact")).content.decode()


def test_widget_is_shown_with_keys(client, turnstile_keys):
    content = client.get(reverse("contacts:contact")).content.decode()

    assert 'data-sitekey="clave-publica"' in content
    assert "challenges.cloudflare.com/turnstile/v0/api.js" in content


def test_cloudflare_approval_lets_the_message_in(client, turnstile_keys, monkeypatch):
    calls = fake_cloudflare(monkeypatch, success=True)

    client.post(SEND, {**data(), turnstile.FIELD: "token"})

    assert ContactMessage.objects.count() == 1
    assert "secret=clave-secreta" in calls[0] and "response=token" in calls[0]


def test_cloudflare_rejection_asks_again(client, turnstile_keys, monkeypatch):
    fake_cloudflare(monkeypatch, success=False)

    response = client.post(SEND, {**data(), turnstile.FIELD: "token"})

    assert response.status_code == 400
    assert not ContactMessage.objects.exists()


def test_missing_token_is_rejected_without_calling_cloudflare(client, turnstile_keys, monkeypatch):
    calls = fake_cloudflare(monkeypatch)

    client.post(SEND, data())

    assert calls == [] and not ContactMessage.objects.exists()


def test_cloudflare_outage_does_not_lose_prayers(client, turnstile_keys, monkeypatch):
    fake_cloudflare(monkeypatch, fail=True)

    client.post(SEND, {**data(), turnstile.FIELD: "token"})

    assert ContactMessage.objects.count() == 1
