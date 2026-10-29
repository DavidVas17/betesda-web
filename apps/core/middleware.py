"""Cabeceras de seguridad que Django no agrega por sí solo."""

from django.conf import settings
from django.http import HttpResponse


def _policy(directives: dict[str, tuple[str, ...]]) -> str:
    return "; ".join(f"{name} {' '.join(values)}".strip() for name, values in directives.items())


class SecurityHeadersMiddleware:
    """Content-Security-Policy y Permissions-Policy.

    El sitio no usa scripts ni estilos en línea, ni recursos de otros dominios (fuentes e
    íconos van en el propio servidor), así que la política puede ser estricta: si algún día
    alguien inyecta HTML, el navegador no ejecuta su código. La única excepción es el mapa
    de Google en la página de contacto.

    Con ``CSP_REPORT_ONLY`` el navegador solo avisa en la consola, sin bloquear: útil para
    probar un cambio de política antes de activarlo.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = _policy(settings.CONTENT_SECURITY_POLICY)
        self.csp_header = (
            "Content-Security-Policy-Report-Only"
            if settings.CSP_REPORT_ONLY
            else "Content-Security-Policy"
        )
        self.permissions = ", ".join(f"{name}=()" for name in settings.PERMISSIONS_POLICY_DENY)
        self.private_prefixes = ("/panel/", f"/{settings.ADMIN_URL}")

    def __call__(self, request):
        response = self.get_response(request)
        if self.csp:
            response.headers.setdefault(self.csp_header, self.csp)
        if self.permissions:
            response.headers.setdefault("Permissions-Policy", self.permissions)
        # Nadie puede incrustar nuestros archivos desde otro sitio.
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if request.path.startswith(self.private_prefixes):
            # El panel y el admin nunca deben aparecer en buscadores.
            response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response


class PendingMigrationsMiddleware:
    """Solo en desarrollo: si el código trae migraciones que la base aún no tiene, muestra
    qué hacer en lugar de un error confuso (por ejemplo, al actualizar con git pull mientras
    el servidor sigue corriendo)."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.up_to_date = False

    def __call__(self, request):
        if not self.up_to_date:
            pending = self._pending()
            if pending:
                return HttpResponse(
                    PENDING_PAGE.format(items="".join(f"<li>{name}</li>" for name in pending)),
                    status=503,
                )
            self.up_to_date = True  # con la base al día, no se vuelve a revisar
        return self.get_response(request)

    @staticmethod
    def _pending() -> list[str]:
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        return [f"{migration.app_label}.{migration.name}" for migration, _ in plan]


PENDING_PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Faltan migraciones</title></head><body>
<h1>La base de datos necesita actualizarse</h1>
<p>El código tiene cambios en la base que todavía no se aplicaron:</p><ul>{items}</ul>
<p>Aplícalos con uno de estos comandos y recarga la página:</p>
<pre>docker compose up -d --force-recreate web</pre>
<pre>docker compose run --rm web python manage.py migrate</pre>
<p><small>Este aviso solo aparece en desarrollo.</small></p></body></html>"""
