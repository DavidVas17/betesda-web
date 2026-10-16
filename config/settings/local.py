from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# En desarrollo la política solo avisa en la consola del navegador: la página de error de
# Django usa estilos en línea y se vería rota si se bloquearan.
CSP_REPORT_ONLY = env.bool("DJANGO_CSP_REPORT_ONLY", default=True)
