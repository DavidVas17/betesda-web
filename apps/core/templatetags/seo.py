"""Ayudas para buscadores y vista previa al compartir (Open Graph, JSON-LD)."""

import json

from django import template
from django.core.serializers.json import DjangoJSONEncoder
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Igual que json_script de Django: dentro de <script> no puede aparecer "</script>".
_ESCAPES = {ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"}


@register.filter
def jsonld(data) -> str:
    """Datos estructurados para Google. No es código ejecutable: la CSP no lo bloquea."""
    payload = json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False).translate(_ESCAPES)
    return format_html('<script type="application/ld+json">{}</script>', mark_safe(payload))  # noqa: S308


@register.simple_tag(takes_context=True)
def absolute(context, url: str) -> str:
    """URL completa (con dominio), como la piden Facebook y WhatsApp."""
    request = context.get("request")
    if not url or url.startswith(("http://", "https://")) or request is None:
        return url or ""
    return request.build_absolute_uri(url)


@register.simple_tag(takes_context=True)
def absolute_static(context, path: str) -> str:
    return absolute(context, static(path))


@register.simple_tag(takes_context=True)
def church_schema(context):
    from apps.core.schedule import active_services
    from apps.core.structured_data import church

    return jsonld(church(context["site"], context["request"], active_services()))


@register.simple_tag(takes_context=True)
def event_schema(context, item):
    from apps.core.structured_data import event

    return jsonld(event(item, context["site"], context["request"]))
