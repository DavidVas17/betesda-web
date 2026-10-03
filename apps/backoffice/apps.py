from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig


class BackofficeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.backoffice"
    verbose_name = "Panel de administracion"


class BetesdaAdminConfig(AdminConfig):
    """Reemplaza a django.contrib.admin para usar el sitio administrativo propio."""

    default_site = "apps.backoffice.sites.BetesdaAdminSite"
