"""Datos de lectura para el dashboard del BackOffice."""

from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.contacts.models import ContactMessage
from apps.core.models import SiteConfiguration
from apps.events.models import Event
from apps.gallery.models import Album, Photo
from apps.news.models import Post

STALE_MESSAGE_HOURS = 48
STALE_DRAFT_DAYS = 14
UPCOMING_WINDOW_DAYS = 7
CHART_WEEKS = 8

STATUS_TONES = {
    ContactMessage.Status.NEW: "danger",
    ContactMessage.Status.IN_PROGRESS: "warn",
    ContactMessage.Status.CLOSED: "ok",
    ContactMessage.Status.SPAM: "neutral",
}


def _url(name: str, *args, query: str = "") -> str:
    url = reverse(f"admin:{name}", args=args)
    return f"{url}?{query}" if query else url


def _weekly_message_counts(now) -> list[dict]:
    today = timezone.localdate(now)
    this_monday = today - timedelta(days=today.weekday())
    mondays = [this_monday - timedelta(weeks=i) for i in range(CHART_WEEKS - 1, -1, -1)]
    since = timezone.make_aware(datetime.combine(mondays[0], time.min))

    counts = dict.fromkeys(mondays, 0)
    for created in ContactMessage.objects.filter(created_at__gte=since).values_list(
        "created_at", flat=True
    ):
        day = timezone.localtime(created).date()
        monday = day - timedelta(days=day.weekday())
        if monday in counts:
            counts[monday] += 1

    highest = max(counts.values()) or 1
    return [
        {
            "label": monday.strftime("%d/%m"),
            "count": total,
            "pct": max(round(total * 100 / highest), 6) if total else 2,
        }
        for monday, total in counts.items()
    ]


def build_dashboard(request) -> dict:
    user = request.user
    now = timezone.now()

    can_messages = user.has_perm("contacts.view_contactmessage")
    can_events = user.has_perm("events.view_event")
    can_posts = user.has_perm("news.view_post")
    can_gallery = user.has_perm("gallery.view_album")
    can_site = user.has_perm("core.view_siteconfiguration")

    kpis: list[dict] = []
    alerts: list[dict] = []
    modules: list[dict] = []
    shortcuts: list[dict] = []
    dashboard: dict = {
        "kpis": kpis,
        "alerts": alerts,
        "modules": modules,
        "shortcuts": shortcuts,
    }

    # --- Mensajes -----------------------------------------------------------------
    if can_messages:
        new_messages = ContactMessage.objects.filter(status=ContactMessage.Status.NEW).count()
        total_messages = ContactMessage.objects.count()
        kpis.append(
            {
                "label": "Mensajes nuevos",
                "value": new_messages,
                "hint": "Pendientes de primera atención",
                "tone": "danger" if new_messages else "ok",
                "url": _url("contacts_contactmessage_changelist", query="status__exact=NEW"),
            }
        )
        modules.append(
            {
                "code": "ME",
                "title": "Mensajes",
                "description": "Atiende consultas, asigna responsables y registra seguimiento.",
                "url": _url("contacts_contactmessage_changelist"),
                "metric": new_messages,
                "metric_label": "nuevos",
                "accent": "rose",
            }
        )
        stale_limit = now - timedelta(hours=STALE_MESSAGE_HOURS)
        stale = ContactMessage.objects.filter(
            status=ContactMessage.Status.NEW, created_at__lte=stale_limit
        ).count()
        if stale:
            alerts.append(
                {
                    "level": "danger",
                    "text": (
                        f"{stale} mensaje(s) llevan más de {STALE_MESSAGE_HOURS} horas "
                        "sin atenderse."
                    ),
                    "url": _url("contacts_contactmessage_changelist", query="status__exact=NEW"),
                    "action": "Atender",
                }
            )
        dashboard["recent_messages"] = [
            {
                "subject": message.subject,
                "name": message.name,
                "kind": message.get_kind_display(),
                "status": message.get_status_display(),
                "tone": STATUS_TONES.get(message.status, "neutral"),
                "ago": message.created_at,
                "url": _url("contacts_contactmessage_change", message.pk),
            }
            for message in ContactMessage.objects.order_by("-created_at")[:5]
        ]
        dashboard["weekly_messages"] = _weekly_message_counts(now) if total_messages else []

    # --- Eventos ------------------------------------------------------------------
    if can_events:
        upcoming = Event.objects.filter(is_published=True, starts_at__gte=now)
        upcoming_total = upcoming.count()
        total_events = Event.objects.count()
        kpis.append(
            {
                "label": "Próximos eventos",
                "value": upcoming_total,
                "hint": "Publicados y por venir",
                "tone": "ok" if upcoming_total else "warn",
                "url": _url("events_event_changelist", query="when=upcoming"),
            }
        )
        modules.append(
            {
                "code": "EV",
                "title": "Eventos",
                "description": "Crea actividades, fechas, ubicaciones, portadas y destacados.",
                "url": _url("events_event_changelist"),
                "add_url": _url("events_event_add") if user.has_perm("events.add_event") else "",
                "add_label": "Nuevo evento",
                "metric": total_events,
                "metric_label": "registrados",
                "accent": "amber",
            }
        )
        dashboard["upcoming_events"] = [
            {
                "title": event.title,
                "starts_at": event.starts_at,
                "location": event.location,
                "featured": event.is_featured,
                "url": _url("events_event_change", event.pk),
            }
            for event in upcoming.order_by("starts_at")[:5]
        ]
        if not upcoming_total:
            alerts.append(
                {
                    "level": "warn",
                    "text": "No hay eventos próximos publicados.",
                    "url": _url("events_event_add"),
                    "action": "Crear evento",
                }
            )
        soon = upcoming.filter(
            starts_at__lte=now + timedelta(days=UPCOMING_WINDOW_DAYS), cover_image=""
        ).count()
        if soon:
            alerts.append(
                {
                    "level": "info",
                    "text": f"{soon} evento(s) de esta semana no tienen imagen de portada.",
                    "url": _url("events_event_changelist", query="when=week"),
                    "action": "Revisar",
                }
            )
        if user.has_perm("events.add_event"):
            shortcuts.append({"label": "Nuevo evento", "url": _url("events_event_add")})

    # --- Noticias -----------------------------------------------------------------
    if can_posts:
        published = Post.objects.filter(status=Post.Status.PUBLISHED).count()
        drafts = Post.objects.filter(status=Post.Status.DRAFT).count()
        total_posts = Post.objects.count()
        kpis.append(
            {
                "label": "Noticias publicadas",
                "value": published,
                "hint": f"{drafts} borrador(es) pendientes",
                "tone": "info",
                "url": _url("news_post_changelist", query="status__exact=PUBLISHED"),
            }
        )
        modules.append(
            {
                "code": "NO",
                "title": "Noticias",
                "description": "Redacta anuncios, publica novedades y administra borradores.",
                "url": _url("news_post_changelist"),
                "add_url": _url("news_post_add") if user.has_perm("news.add_post") else "",
                "add_label": "Nueva noticia",
                "metric": total_posts,
                "metric_label": "publicaciones",
                "accent": "blue",
            }
        )
        dashboard["recent_drafts"] = [
            {
                "title": post.title,
                "updated_at": post.updated_at,
                "url": _url("news_post_change", post.pk),
            }
            for post in Post.objects.filter(status=Post.Status.DRAFT).order_by("-updated_at")[:5]
        ]
        old_drafts = Post.objects.filter(
            status=Post.Status.DRAFT, updated_at__lte=now - timedelta(days=STALE_DRAFT_DAYS)
        ).count()
        if old_drafts:
            alerts.append(
                {
                    "level": "info",
                    "text": (
                        f"{old_drafts} borrador(es) llevan más de {STALE_DRAFT_DAYS} días "
                        "sin cambios."
                    ),
                    "url": _url("news_post_changelist", query="status__exact=DRAFT"),
                    "action": "Ver borradores",
                }
            )
        if user.has_perm("news.add_post"):
            shortcuts.append({"label": "Nueva noticia", "url": _url("news_post_add")})

    # --- Galería ------------------------------------------------------------------
    if can_gallery:
        albums = Album.objects.filter(is_published=True).count()
        total_albums = Album.objects.count()
        total_photos = Photo.objects.count()
        kpis.append(
            {
                "label": "Álbumes publicados",
                "value": albums,
                "hint": f"{total_photos} fotografía(s) en total",
                "tone": "info",
                "url": _url("gallery_album_changelist", query="is_published__exact=1"),
            }
        )
        modules.append(
            {
                "code": "GA",
                "title": "Galería",
                "description": "Organiza álbumes y fotografías de las actividades de la iglesia.",
                "url": _url("gallery_album_changelist"),
                "add_url": _url("gallery_album_add") if user.has_perm("gallery.add_album") else "",
                "add_label": "Nuevo álbum",
                "metric": total_albums,
                "metric_label": "álbumes",
                "accent": "violet",
            }
        )
        if user.has_perm("gallery.add_album"):
            shortcuts.append({"label": "Nuevo álbum", "url": _url("gallery_album_add")})

    # --- Configuración del sitio --------------------------------------------------
    if can_site:
        config = SiteConfiguration.objects.first()
        modules.append(
            {
                "code": "CO",
                "title": "Configuración",
                "description": "Actualiza datos institucionales, contacto, dirección y enlaces.",
                "url": (
                    _url("core_siteconfiguration_change", config.pk)
                    if config
                    else _url("core_siteconfiguration_add")
                ),
                "metric": "OK" if config else "—",
                "metric_label": "sitio",
                "accent": "green",
            }
        )
        if config is None:
            alerts.append(
                {
                    "level": "warn",
                    "text": "Falta la configuración general del sitio.",
                    "url": _url("core_siteconfiguration_add"),
                    "action": "Configurar",
                }
            )
        else:
            labels = {
                "phone": "teléfono",
                "email": "correo",
                "address": "dirección",
                "facebook_url": "Facebook",
                "map_url": "mapa",
            }
            missing = [label for field, label in labels.items() if not getattr(config, field)]
            dashboard["site_checklist"] = {
                "done": len(labels) - len(missing),
                "total": len(labels),
                "missing": missing,
                "url": _url("core_siteconfiguration_change", config.pk),
            }
            if missing:
                alerts.append(
                    {
                        "level": "info",
                        "text": (
                            "La configuración del sitio está incompleta: "
                            + ", ".join(missing)
                            + "."
                        ),
                        "url": _url("core_siteconfiguration_change", config.pk),
                        "action": "Completar",
                    }
                )

    # --- Usuarios: solo el superusuario raíz -------------------------------------
    if user.is_superuser:
        user_model = get_user_model()
        active_users = user_model.objects.filter(
            is_staff=True, is_active=True, is_superuser=False
        ).count()
        modules.append(
            {
                "code": "US",
                "title": "Usuarios",
                "description": "Crea, activa, desactiva y administra las cuentas del BackOffice.",
                "url": _url("accounts_user_changelist"),
                "add_url": _url("accounts_user_add"),
                "add_label": "Nuevo usuario",
                "metric": active_users,
                "metric_label": "activos",
                "accent": "slate",
            }
        )
        shortcuts.append({"label": "Nuevo usuario", "url": _url("accounts_user_add")})

    module_order = {"EV": 10, "NO": 20, "GA": 30, "ME": 40, "CO": 50, "US": 60}
    modules.sort(key=lambda item: module_order.get(item["code"], 999))

    dashboard["has_content"] = bool(kpis or modules or shortcuts)
    return dashboard
