from django.contrib import admin

from .dashboard import build_dashboard


class BetesdaAdminSite(admin.AdminSite):
    site_header = "Betesda Rosa de Sarón"
    site_title = "Panel Betesda"
    index_title = "Panel de administración"
    index_template = "admin/dashboard.html"
    site_url = "/"
    # El panel funciona como un BackOffice propio; la navegación principal vive en el
    # dashboard y no en el listado técnico de aplicaciones/modelos de Django.
    enable_nav_sidebar = False
    empty_value_display = "—"

    def each_context(self, request):
        context = super().each_context(request)
        context["bo_new_messages"] = self._new_messages_count(request)
        return context

    @staticmethod
    def _new_messages_count(request) -> int:
        user = request.user
        if not (user.is_authenticated and user.has_perm("contacts.view_contactmessage")):
            return 0
        from apps.contacts.models import ContactMessage

        return ContactMessage.objects.filter(status=ContactMessage.Status.NEW).count()

    def index(self, request, extra_context=None):
        extra_context = {**(extra_context or {}), "dashboard": build_dashboard(request)}
        return super().index(request, extra_context)
