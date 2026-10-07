from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Event


def upcoming_events(limit: int | None = 6) -> QuerySet[Event]:
    now = timezone.now()
    events = (
        Event.objects.filter(is_published=True)
        .filter(Q(ends_at__gte=now) | Q(ends_at__isnull=True, starts_at__gte=now))
        .order_by("starts_at", "pk")
    )
    return events[:limit] if limit is not None else events
