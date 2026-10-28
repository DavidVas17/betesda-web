from datetime import UTC, timedelta

from django.conf import settings
from django.db import DatabaseError, connections
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone

from apps.events.selectors import upcoming_events
from apps.news.selectors import published_posts

from .models import ChurchValue, Ministry
from .schedule import schedule_context


def home(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "home.html",
        {
            "events": upcoming_events(limit=3),
            "posts": published_posts().order_by("-is_featured", "-published_at")[:3],
            "ministries": Ministry.objects.filter(is_active=True)[:3],
            **schedule_context(),
        },
    )


def about(request: HttpRequest) -> HttpResponse:
    values = ChurchValue.objects.filter(is_active=True)
    return render(request, "core/about.html", {"values": values})


def ministries(request: HttpRequest) -> HttpResponse:
    ministries = Ministry.objects.filter(is_active=True)
    return render(request, "core/ministries.html", {"ministries": ministries})


def favicon(request: HttpRequest) -> HttpResponse:
    return redirect(static("images/favicon-betesda.ico"), permanent=True)


def robots_txt(request: HttpRequest) -> HttpResponse:
    """El panel no se indexa. La ruta del admin no se menciona: listarla aquí la revelaría."""
    lines = ["User-agent: *", "Disallow: /panel/", "Disallow: /health/", ""]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def security_txt(request: HttpRequest) -> HttpResponse:
    """Contacto para reportar vulnerabilidades (RFC 9116)."""
    contact = settings.SECURITY_CONTACT_EMAIL
    if not contact:
        return HttpResponse(status=404)
    expires = (timezone.now() + timedelta(days=365)).replace(microsecond=0)
    lines = [
        f"Contact: mailto:{contact}",
        f"Expires: {expires.astimezone(UTC).isoformat().replace('+00:00', 'Z')}",
        "Preferred-Languages: es, en",
        f"Canonical: {request.build_absolute_uri('/.well-known/security.txt')}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def live(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok", "service": "betesda-web"})


def ready(request: HttpRequest) -> JsonResponse:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "unavailable", "database": "error"}, status=503)
    return JsonResponse({"status": "ok", "database": "connected"})


def bad_request(request: HttpRequest, exception: Exception) -> HttpResponse:
    return render(request, "errors/400.html", status=400)


def permission_denied(request: HttpRequest, exception: Exception) -> HttpResponse:
    return render(request, "errors/403.html", status=403)


def page_not_found(request: HttpRequest, exception: Exception) -> HttpResponse:
    return render(request, "errors/404.html", status=404)


def server_error(request: HttpRequest) -> HttpResponse:
    return render(request, "errors/500.html", status=500)
