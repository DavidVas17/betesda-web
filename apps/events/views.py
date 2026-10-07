from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Event
from .selectors import upcoming_events


def event_list(request):
    past = request.GET.get("vista") == "anteriores"
    if past:
        now = timezone.now()
        events = (
            Event.objects.filter(is_published=True)
            .filter(Q(ends_at__lt=now) | Q(ends_at__isnull=True, starts_at__lt=now))
            .order_by("-starts_at", "-pk")
        )
    else:
        events = upcoming_events(limit=None)
    page = Paginator(events, 9).get_page(request.GET.get("pagina"))
    return render(request, "events/list.html", {"page_obj": page, "past": past})


def detail(request, slug):
    event = get_object_or_404(Event, slug=slug, is_published=True)
    return render(request, "events/detail.html", {"event": event})
