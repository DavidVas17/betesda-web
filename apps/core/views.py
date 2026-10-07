from django.db import DatabaseError, connections
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static

from apps.events.selectors import upcoming_events
from apps.news.selectors import published_posts

from .content import MINISTRIES, VALUES


def home(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "home.html",
        {
            "events": upcoming_events(limit=3),
            "posts": published_posts().order_by("-is_featured", "-published_at")[:3],
            "ministries": MINISTRIES[:3],
        },
    )


def about(request: HttpRequest) -> HttpResponse:
    return render(request, "core/about.html", {"values": VALUES})


def ministries(request: HttpRequest) -> HttpResponse:
    return render(request, "core/ministries.html", {"ministries": MINISTRIES})


def favicon(request: HttpRequest) -> HttpResponse:
    return redirect(static("images/favicon.ico"), permanent=True)


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
