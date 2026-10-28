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
