from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    DJANGO_LOG_LEVEL=(str, "INFO"),
)

if env.bool("DJANGO_READ_DOT_ENV_FILE", default=True):
    env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

# Ruta de la administración técnica (solo superusuario). En producción conviene usar una
# ruta propia en lugar de la conocida "admin/". Debe terminar en "/" y no empezar con "/".
ADMIN_URL = env.str("DJANGO_ADMIN_URL", default="admin/").strip("/") + "/"
if ADMIN_URL in {"/", "panel/"}:
    raise ValueError("DJANGO_ADMIN_URL debe ser una ruta propia, distinta de la raíz y del panel.")

INSTALLED_APPS = [
    # El panel propio va antes del admin de Django para poder sobrescribir sus plantillas.
    "apps.backoffice.apps.BackofficeConfig",
    "apps.backoffice.apps.BetesdaAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "apps.accounts.apps.AccountsConfig",
    "apps.core.apps.CoreConfig",
    "apps.events.apps.EventsConfig",
    "apps.news.apps.NewsConfig",
    "apps.gallery.apps.GalleryConfig",
    "apps.contacts.apps.ContactsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "apps.accounts.alerts.DeviceCookieMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.backoffice.panel.security.TwoFactorEnforcementMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Después de los mensajes: avisa por qué pide cambiar la contraseña.
    "apps.backoffice.panel.security.PasswordUpgradeMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.public_site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL"),
}
DATABASES["default"].update(
    {
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    # 10 caracteres como mínimo: una frase corta es más segura y fácil de recordar.
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/panel/ingresar/"
# El enlace para restablecer la contraseña vence a las 2 horas (Django usa 3 días).
PASSWORD_RESET_TIMEOUT = env.int("PASSWORD_RESET_TIMEOUT", default=2 * 3600)
LOGIN_REDIRECT_URL = "/panel/"
LOGOUT_REDIRECT_URL = "/"
# Verificación en dos pasos obligatoria para el superusuario y Administración de la iglesia.
TWO_FACTOR_ENFORCE = env.bool("TWO_FACTOR_ENFORCE", default=True)
# Acciones delicadas (exportar mensajes, cuentas del equipo) piden la contraseña otra vez si
# se escribió hace más de estos minutos.
RECENT_AUTH_REQUIRED = True
RECENT_AUTH_MINUTES = env.int("RECENT_AUTH_MINUTES", default=10)
# Minutos para escribir el código después de la contraseña.
TWO_FACTOR_PENDING_MINUTES = 5
# La sesión del panel se cierra tras estas horas sin actividad: cada visita reinicia el
# plazo. Protege una cuenta abierta en una computadora compartida de la iglesia.
SESSION_COOKIE_AGE = env.int("PANEL_SESSION_HOURS", default=8) * 3600
SESSION_SAVE_EVERY_REQUEST = True

LANGUAGE_CODE = "es-gt"
# El sitio solo existe en español: así un navegador en otro idioma no mezcla fechas en inglés.
LANGUAGES = [("es-gt", "Español (Guatemala)")]
TIME_ZONE = "America/Guatemala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# Correo: EMAIL_URL define el servidor (por ejemplo smtp+tls://usuario:clave@smtp.dominio:587).
# Sin configurarlo, los correos se muestran en la consola en lugar de enviarse.
globals().update(env.email_url("EMAIL_URL", default="consolemail://"))
DEFAULT_FROM_EMAIL = env.str(
    "DEFAULT_FROM_EMAIL", default="Betesda Rosa de Sarón <no-responder@localhost>"
)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
# Buzón de la iglesia que recibe siempre el aviso de cada petición o mensaje nuevo, además
# del equipo que atiende mensajes. Separados por coma.
CONTACT_NOTIFY_EMAILS = env.list("CONTACT_NOTIFY_EMAILS", default=[])
# Correos extra que reciben los avisos de seguridad (bloqueos, cuentas nuevas, privilegios),
# además del superusuario y Administración de la iglesia. Separados por coma.
SECURITY_ALERT_EMAILS = env.list("SECURITY_ALERT_EMAILS", default=[])
# Correo público para reportar vulnerabilidades (/.well-known/security.txt).
SECURITY_CONTACT_EMAIL = env.str("SECURITY_CONTACT_EMAIL", default="")
# Dirección pública del sitio, para los enlaces de correos enviados fuera de una visita.
SITE_URL = env.str("SITE_URL", default="")

DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Política de contenido: solo recursos del propio sitio, sin código en línea. Ver
# apps/core/middleware.py. El mapa de contacto se carga desde Google Maps.
CONTENT_SECURITY_POLICY = {
    "default-src": ("'self'",),
    "script-src": ("'self'",),
    "style-src": ("'self'",),
    "img-src": ("'self'", "data:"),
    "font-src": ("'self'",),
    "connect-src": ("'self'",),
    "frame-src": ("https://www.google.com", "https://maps.google.com"),
    "object-src": ("'none'",),
    "base-uri": ("'self'",),
    "form-action": ("'self'",),
    "frame-ancestors": ("'none'",),
}
CSP_REPORT_ONLY = env.bool("DJANGO_CSP_REPORT_ONLY", default=False)
# Funciones del navegador que el sitio nunca usa.
PERMISSIONS_POLICY_DENY = ("camera", "microphone", "geolocation", "payment", "usb")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": env("DJANGO_LOG_LEVEL"),
    },
}

# Formulario público: máximo de mensajes por IP dentro de la ventana (en segundos).
CONTACT_RATE_LIMIT = (
    env.int("CONTACT_RATE_LIMIT_COUNT", default=5),
    env.int("CONTACT_RATE_LIMIT_SECONDS", default=600),
)
# Cuántos días se guardan los mensajes (ver apps/contacts/retention.py). Los nuevos o en
# seguimiento no se eliminan nunca de forma automática.
MESSAGE_RETENTION_DAYS = env.int("MESSAGE_RETENTION_DAYS", default=365)
SPAM_RETENTION_DAYS = env.int("SPAM_RETENTION_DAYS", default=30)
IP_RETENTION_DAYS = env.int("IP_RETENTION_DAYS", default=90)
# Trampa de tiempo del formulario: segundos mínimos para enviarlo y vigencia de la firma.
CONTACT_TIME_TRAP = (
    env.int("CONTACT_MIN_SECONDS", default=3),
    env.int("CONTACT_FORM_MAX_AGE", default=2 * 3600),
)
# Máximo de mensajes desde un mismo correo y ventana en segundos.
CONTACT_EMAIL_RATE_LIMIT = (
    env.int("CONTACT_EMAIL_RATE_LIMIT_COUNT", default=3),
    env.int("CONTACT_EMAIL_RATE_LIMIT_SECONDS", default=3600),
)
# Cloudflare Turnstile (opcional): verificación "no soy un robot" en el formulario.
TURNSTILE_SITE_KEY = env.str("TURNSTILE_SITE_KEY", default="")
TURNSTILE_SECRET_KEY = env.str("TURNSTILE_SECRET_KEY", default="")
if TURNSTILE_SITE_KEY:
    for _directive in ("script-src", "frame-src", "connect-src"):
        CONTENT_SECURITY_POLICY[_directive] += ("https://challenges.cloudflare.com",)
# Detrás de un proxy propio (Caddy en producción) la IP del visitante llega en X-Forwarded-For.
TRUST_X_FORWARDED_FOR = env.bool("DJANGO_TRUST_X_FORWARDED_FOR", default=False)
# Ingreso al panel y a la administración técnica: fallos permitidos por usuario e IP, por IP
# (con cualquier usuario) y la ventana en segundos tras la cual se olvidan.
LOGIN_RATE_LIMIT = (
    env.int("LOGIN_RATE_LIMIT_PER_USER", default=5),
    env.int("LOGIN_RATE_LIMIT_PER_IP", default=20),
    env.int("LOGIN_RATE_LIMIT_SECONDS", default=900),
)
