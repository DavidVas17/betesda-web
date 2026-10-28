from django.contrib.admin.models import LogEntry
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.accounts import two_factor
from apps.contacts.models import ContactMessage
from apps.events.models import Event
from apps.gallery.models import Album
from apps.news.models import Post

from .access import panel_required
from .utils import panel_render, query_url


@panel_required()
@require_GET
def dashboard(request):
    user = request.user
    now = timezone.now()
    kpis, quick_actions = [], []
    recent_messages, upcoming_events, recent_posts = [], [], []
    if user.has_perm("contacts.view_contactmessage"):
        incoming = ContactMessage.objects.filter(status=ContactMessage.Status.NEW)
        kpis.append(
            {
                "label": "Mensajes nuevos",
                "value": incoming.count(),
                "description": "Personas que esperan una respuesta",
                "icon": "inbox",
                "tone": "gold",
                "url": query_url("panel:message_list", status="NEW"),
            }
        )
        recent_messages = (
            ContactMessage.objects.select_related("assigned_to")
            .filter(status__in=(ContactMessage.Status.NEW, ContactMessage.Status.IN_PROGRESS))
            .order_by("-created_at", "-pk")[:5]
        )
    if user.has_perm("events.view_event"):
        upcoming = Event.objects.filter(is_published=True, starts_at__gte=now)
        kpis.append(
            {
                "label": "Próximos eventos",
                "value": upcoming.count(),
                "description": "Encuentros publicados por venir",
                "icon": "calendar",
                "tone": "green",
                "url": reverse("panel:event_list"),
            }
        )
        upcoming_events = upcoming.order_by("starts_at", "pk")[:4]
    if user.has_perm("news.view_post"):
        kpis.append(
            {
                "label": "Noticias publicadas",
                "value": Post.objects.filter(
                    status=Post.Status.PUBLISHED, published_at__lte=now
                ).count(),
                "description": "Novedades disponibles en el sitio",
                "icon": "news",
                "tone": "blue",
                "url": reverse("panel:news_list"),
            }
        )
        recent_posts = Post.objects.select_related("author").order_by("-created_at", "-pk")[:4]
    if user.has_perm("gallery.view_album"):
        kpis.append(
            {
                "label": "Álbumes publicados",
                "value": Album.objects.filter(is_published=True).count(),
                "description": "Recuerdos compartidos con la comunidad",
                "icon": "image",
                "tone": "neutral",
                "url": reverse("panel:album_list"),
            }
        )
    for label, route, permission, description, icon in (
        (
            "Crear evento",
            "event_create",
            "events.add_event",
            "Prepara el próximo encuentro.",
            "calendar",
        ),
        (
            "Escribir noticia",
            "news_create",
            "news.add_post",
            "Comparte una novedad de la iglesia.",
            "news",
        ),
        (
            "Crear álbum",
            "album_create",
            "gallery.add_album",
            "Reúne las fotografías de un evento.",
            "image",
        ),
        (
            "Revisar mensajes",
            "message_list",
            "contacts.view_contactmessage",
            "Acompaña a quienes nos escriben.",
            "inbox",
        ),
    ):
        if user.has_perm(permission):
            quick_actions.append(
                {
                    "label": label,
                    "url": reverse(f"panel:{route}"),
                    "description": description,
                    "icon": icon,
                }
            )
    return panel_render(
        request,
        "panel/dashboard.html",
        {
            "suggest_two_factor": not two_factor.is_enabled(request.user),
            "kpis": kpis,
            "quick_actions": quick_actions,
            "recent_messages": recent_messages,
            "upcoming_events": upcoming_events,
            "recent_posts": recent_posts,
            "recent_activity": LogEntry.objects.select_related("user", "content_type").order_by(
                "-action_time", "-pk"
            )[:5]
            if user.has_perm("accounts.view_activity")
            else [],
            "greeting": f"Hola, {user.first_name or user.username}",
            "today": timezone.localdate(),
        },
        title="Inicio",
        subtitle="Un espacio para cuidar y compartir la vida de nuestra comunidad.",
    )
