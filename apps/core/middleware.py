"""Cabeceras de seguridad que Django no agrega por sí solo."""

from django.conf import settings


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
