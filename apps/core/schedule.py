"""Horarios de culto para el sitio público: agrupados por día y el próximo en llegar."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone

from .models import ServiceTime

# Si un culto no tiene hora de finalización, se considera "en curso" durante este tiempo.
DEFAULT_DURATION = timedelta(hours=2)


@dataclass(frozen=True)
class NextService:
    service: ServiceTime
    starts: datetime
    label: str  # "Ahora", "Hoy", "Mañana" o el nombre del día
    in_progress: bool = False


def active_services():
    return list(ServiceTime.objects.filter(is_active=True))


def by_day(services):
    """[(nombre del día, [horarios])] en orden de la semana, solo días con horario."""
    days = {}
    for service in services:
        days.setdefault(service.day, []).append(service)
    return [(ServiceTime.Day(day).label, days[day]) for day in sorted(days)]


def next_service(services, now=None) -> NextService | None:
    """El próximo culto a partir de ``now`` (hora local), o el que está en curso."""
    if not services:
        return None
    now = timezone.localtime(now)
    best = None
    for service in services:
        days_ahead = (service.day - now.weekday()) % 7
        start = now.replace(
            hour=service.starts_at.hour,
            minute=service.starts_at.minute,
            second=0,
            microsecond=0,
        ) + timedelta(days=days_ahead)
        if service.ends_at:
            end = start.replace(hour=service.ends_at.hour, minute=service.ends_at.minute)
        else:
            end = start + DEFAULT_DURATION
        if end <= now:
            start += timedelta(days=7)
            end += timedelta(days=7)
        if best is None or start < best[0]:
            best = (start, end, service)
    start, end, service = best
    in_progress = start <= now < end
    delta = (start.date() - now.date()).days
    if in_progress:
        label = "Ahora"
    elif delta == 0:
        label = "Hoy"
    elif delta == 1:
        label = "Mañana"
    else:
        label = ServiceTime.Day(service.day).label
    return NextService(service=service, starts=start, label=label, in_progress=in_progress)


def schedule_context(now=None) -> dict:
    services = active_services()
    return {
        "service_days": by_day(services),
        "next_service": next_service(services, now),
    }
