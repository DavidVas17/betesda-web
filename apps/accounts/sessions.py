"""Sesiones abiertas de una cuenta."""

from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.utils import timezone


def end_other_sessions(request) -> int:
    """Elimina las demás sesiones de la persona; la actual sigue abierta.

    Las sesiones se guardan en la base y son pocas (un equipo pequeño), así que basta
    revisarlas una por una.
    """
    current = request.session.session_key
    user_id = str(request.user.pk)
    closed = 0
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        if session.session_key == current:
            continue
        if str(session.get_decoded().get(SESSION_KEY)) == user_id:
            session.delete()
            closed += 1
    return closed
