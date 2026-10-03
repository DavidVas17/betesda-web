from django.db import DatabaseError, connections
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from django.db.models import Q
from django.utils import timezone

from apps.events.models import Event

def home(request: HttpRequest) -> HttpResponse:
    now = timezone.now()

    events = (
        Event.objects
        .filter(is_published=True)
        .filter(
            Q(ends_at__gte=now)
            | Q(ends_at__isnull=True, starts_at__gte=now)
        )
        .order_by("starts_at")[:6]
    )

    return render(
        request,
        "home.html",
        {
            "events": events,
        },
    )
    
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
