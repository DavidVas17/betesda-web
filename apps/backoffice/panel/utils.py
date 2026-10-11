from urllib.parse import urlencode

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse

from apps.contacts.models import ContactMessage


def panel_context(request, active="dashboard", title="Inicio", subtitle=""):
    user = request.user
    new_messages = (
        ContactMessage.objects.filter(status=ContactMessage.Status.NEW).count()
        if user.has_perm("contacts.view_contactmessage")
        else 0
    )
    sections = [
        ("Inicio", "dashboard", "dashboard", None),
        ("Eventos", "event_list", "calendar", "events.view_event"),
        ("Noticias", "news_list", "news", "news.view_post"),
        ("Galería", "album_list", "image", "gallery.view_album"),
        ("Mensajes", "message_list", "inbox", "contacts.view_contactmessage"),
        ("Configuración", "settings", "settings", "core.view_siteconfiguration"),
    ]
    navigation = []
    active_keys = {
        "event_list": "events",
        "news_list": "news",
        "album_list": "gallery",
        "message_list": "messages",
        "settings": "settings",
        "dashboard": "dashboard",
    }
    for label, route, icon, permission in sections:
        allowed = permission is None or user.has_perm(permission)
        if route == "settings":
            allowed = (
                allowed
                or user.has_perm("core.add_siteconfiguration")
                or user.has_perm("core.change_siteconfiguration")
            )
        if allowed:
            navigation.append(
                {
                    "label": label,
                    "url": reverse(f"panel:{route}"),
                    "icon": icon,
                    "active": active == active_keys[route],
                    "badge": new_messages if route == "message_list" else 0,
                }
            )
    if user.is_superuser:
        for label, route, icon in (
            ("Usuarios", "user_list", "users"),
            ("Actividad", "activity", "activity"),
        ):
            navigation.append(
                {
                    "label": label,
                    "url": reverse(f"panel:{route}"),
                    "icon": icon,
                    "active": active == ("users" if route == "user_list" else "activity"),
                    "badge": 0,
                }
            )
    return {
        "panel_navigation": navigation,
        "panel_new_messages": new_messages,
        "panel_active": active,
        "panel_title": title,
        "panel_subtitle": subtitle,
    }


def panel_render(
    request, template, context=None, *, active="dashboard", title="Inicio", subtitle=""
):
    return render(
        request,
        template,
        {**panel_context(request, active, title, subtitle), **(context or {})},
    )


def paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get("pagina"))


def pagination_query(request):
    parameters = request.GET.copy()
    parameters.pop("pagina", None)
    return parameters.urlencode()


def audit(request, obj, flag=CHANGE, message="Actualización desde el panel"):
    """Registra la operación sin contraseñas ni el cuerpo de solicitudes privadas."""
    description = f"Solicitud #{obj.pk}" if isinstance(obj, ContactMessage) else str(obj)
    return LogEntry.objects.create(
        user_id=request.user.pk,
        content_type=ContentType.objects.get_for_model(obj, for_concrete_model=False),
        object_id=str(obj.pk),
        object_repr=description[:200],
        action_flag=flag,
        change_message=message,
    )


def query_url(route, **parameters):
    return f"{reverse(route)}?{urlencode(parameters)}"
