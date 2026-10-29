from .base import *  # noqa: F403

SECRET_KEY = "test-only-secret-key"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Las pruebas que la necesitan la activan; así el resto no tiene que configurar 2FA.
TWO_FACTOR_ENFORCE = False
# La trampa de tiempo se prueba aparte; el resto de pruebas envía el formulario al instante.
CONTACT_TIME_TRAP = None
# La reconfirmación se prueba aparte (tests/test_recent_auth.py).
RECENT_AUTH_REQUIRED = False

# Las pruebas no dependen del .env de quien las corre (dentro de Docker se carga el .env del
# proyecto): correos, claves externas y límites quedan fijos aquí.
CONTACT_NOTIFY_EMAILS = []
SECURITY_ALERT_EMAILS = []
SECURITY_CONTACT_EMAIL = ""
SITE_URL = ""
TURNSTILE_SITE_KEY = ""
TURNSTILE_SECRET_KEY = ""
DEFAULT_FROM_EMAIL = "Betesda Rosa de Sarón <no-responder@localhost>"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CONTACT_RATE_LIMIT = (5, 600)
CONTACT_EMAIL_RATE_LIMIT = (3, 3600)
LOGIN_RATE_LIMIT = (5, 20, 900)
MESSAGE_RETENTION_DAYS = 365
SPAM_RETENTION_DAYS = 30
IP_RETENTION_DAYS = 90
RECENT_AUTH_MINUTES = 10
PASSWORD_RESET_TIMEOUT = 2 * 3600
SESSION_COOKIE_AGE = 8 * 3600
