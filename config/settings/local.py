from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

# El correo lo decide EMAIL_URL (ver base.py): sin definirlo, los correos se muestran en la
# consola; con un servidor real (por ejemplo Gmail) se envían de verdad, útil para probar.
# En desarrollo la política solo avisa en la consola del navegador: la página de error de
# Django usa estilos en línea y se vería rota si se bloquearan.
CSP_REPORT_ONLY = env.bool("DJANGO_CSP_REPORT_ONLY", default=True)

# Si falta aplicar migraciones (por ejemplo tras un git pull), lo dice con el comando a correr.
MIDDLEWARE = [*MIDDLEWARE, "apps.core.middleware.PendingMigrationsMiddleware"]  # noqa: F405
