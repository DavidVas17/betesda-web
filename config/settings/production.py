from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env

DEBUG = False

if SECRET_KEY.startswith("change-me"):  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY debe ser un secreto fuerte en produccion.")
if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS es obligatorio en produccion.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
USE_X_FORWARDED_HOST = env.bool("DJANGO_USE_X_FORWARDED_HOST", default=True)
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Caddy está delante de Django y escribe la IP real del visitante en X-Forwarded-For.
TRUST_X_FORWARDED_FOR = env.bool("DJANGO_TRUST_X_FORWARDED_FOR", default=True)

# Errores 500 por correo a quien mantiene el sitio. Por defecto, a SECURITY_ALERT_EMAILS.
# El reporte no incluye contraseñas, cookies ni el contenido de las peticiones de oración
# (las vistas de contacto marcan esos campos como sensibles).
ADMINS = [(email, email) for email in env.list("ERROR_EMAILS", default=SECURITY_ALERT_EMAILS)]  # noqa: F405
SERVER_EMAIL = DEFAULT_FROM_EMAIL  # noqa: F405
EMAIL_SUBJECT_PREFIX = "[Betesda · Error] "
LOGGING["handlers"]["mail_admins"] = {  # noqa: F405
    "class": "django.utils.log.AdminEmailHandler",
    "level": "ERROR",
    "include_html": False,
}
LOGGING["loggers"] = {  # noqa: F405
    "django.request": {
        "handlers": ["console", "mail_admins"],
        "level": "ERROR",
        "propagate": False,
    },
}
