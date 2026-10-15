"""Datos de red de una petición."""

import ipaddress

from django.conf import settings


def client_ip(request) -> str | None:
    """IP del visitante.

    En producción el sitio está detrás de Caddy: ``REMOTE_ADDR`` es la IP de Caddy y la del
    visitante llega en ``X-Forwarded-For``. Solo se confía en ese encabezado cuando
    ``TRUST_X_FORWARDED_FOR`` está activo; se toma la última IP, que es la que agregó nuestro
    propio proxy y un visitante no puede falsificar.
    """
    candidate = request.META.get("REMOTE_ADDR", "")
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            candidate = hops[-1]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None
