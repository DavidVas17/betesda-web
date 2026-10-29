"""Guía rápida del panel: cómo hacer cada tarea, según lo que la persona puede hacer."""

from dataclasses import dataclass, field

from django.urls import reverse
from django.views.decorators.http import require_GET

from .access import panel_required
from .utils import panel_render


@dataclass(frozen=True)
class Topic:
    key: str
    icon: str
    title: str
    summary: str
    steps: tuple[str, ...]
    permission: str | None = None
    link: tuple[str, str] | None = None  # (texto, nombre de la ruta)
    tips: tuple[str, ...] = field(default_factory=tuple)


TOPICS = (
    Topic(
        key="eventos",
        icon="calendar",
        title="Publicar un evento",
        summary="Cultos especiales, vigilias, campamentos y actividades.",
        permission="events.add_event",
        steps=(
            "Ve a Eventos y toca «Nuevo evento».",
            "Escribe el título y un resumen corto: es lo que se ve en la tarjeta.",
            "Elige la fecha, la hora y el lugar. Si dura varios días, agrega la hora de fin.",
            "Sube una imagen horizontal (por ejemplo 1600 × 900). El sitio la optimiza solo.",
            "Activa «Publicado» para que aparezca en el sitio. «Destacado» lo lleva al inicio.",
        ),
        tips=(
            "Si tu rol es Colaboración, se guarda como borrador y Coordinación lo publica.",
            "Los eventos pasados se mueven solos a «Anteriores».",
        ),
        link=("Ir a Eventos", "panel:event_list"),
    ),
    Topic(
        key="noticias",
        icon="news",
        title="Escribir una noticia o anuncio",
        summary="Avisos, cambios de horario y testimonios.",
        permission="news.add_post",
        steps=(
            "Ve a Noticias y toca «Nueva noticia».",
            "El título y el extracto son lo primero que se lee: que sean claros.",
            "Escribe el texto. Deja una línea en blanco para separar párrafos.",
            "Elige «Borrador» para seguir después o «Publicado» para mostrarla ya.",
        ),
        link=("Ir a Noticias", "panel:news_list"),
    ),
    Topic(
        key="galeria",
        icon="image",
        title="Subir fotos a la galería",
        summary="Álbumes de cada actividad.",
        permission="gallery.add_album",
        steps=(
            "Ve a Galería y crea un álbum con el nombre y la fecha de la actividad.",
            "En el álbum, arrastra las fotos o elígelas: hasta 30 a la vez, de 8 MB cada una.",
            "Escribe un texto alternativo que describa las fotos (ayuda a personas con lector "
            "de pantalla).",
            "Publica el álbum cuando esté listo.",
        ),
        tips=(
            "La ubicación GPS y los datos del teléfono se quitan solos de cada foto.",
            "Evita fotos donde se vean niños sin permiso de sus padres.",
        ),
        link=("Ir a Galería", "panel:album_list"),
    ),
    Topic(
        key="mensajes",
        icon="inbox",
        title="Atender una petición de oración o mensaje",
        summary="Lo que la comunidad escribe desde el sitio.",
        permission="contacts.view_contactmessage",
        steps=(
            "Te llega un correo cuando entra una solicitud. Ábrela desde el enlace o en Mensajes.",
            "Asígnala a la persona que la acompañará y cambia el estado a «En seguimiento».",
            "Usa «Responder por correo» para escribirle; puedes partir de una respuesta lista.",
            "Anota en «Notas del equipo» lo que hicieron. La persona no las ve.",
            "Cuando terminen, márcala «Cerrada». Se elimina sola después de un año.",
        ),
        tips=(
            "Lo que el sitio detecta como spam queda en «No deseado» y no avisa a nadie.",
            "Las peticiones son confidenciales: no las compartas fuera del equipo.",
        ),
        link=("Ir a Mensajes", "panel:message_list"),
    ),
    Topic(
        key="iglesia",
        icon="church",
        title="Horarios, ministerios y datos de la iglesia",
        summary="Lo que se muestra en Inicio, Nosotros y Ministerios.",
        permission="core.change_servicetime",
        steps=(
            "En «Nuestra iglesia» edita los horarios de culto: el inicio muestra el próximo "
            "servicio automáticamente.",
            "Ahí mismo están los ministerios y los valores, con su orden.",
            "En «Configuración» cambias teléfono, dirección, redes, misión y visión.",
        ),
        link=("Ir a Nuestra iglesia", "panel:institution"),
    ),
    Topic(
        key="equipo",
        icon="users",
        title="Agregar a alguien al equipo",
        summary="Cuentas y roles.",
        permission="accounts.manage_team",
        steps=(
            "Ve a Usuarios y toca «Agregar persona al equipo».",
            "Escribe su usuario, correo y una contraseña temporal de 10 caracteres o más.",
            "Elige sus roles según lo que hará. Se pueden combinar.",
            "Comparte la contraseña por un medio privado y pídele que la cambie en Mi cuenta.",
        ),
        tips=(
            "Si alguien deja el equipo, desactiva su cuenta en lugar de borrarla.",
            "Si perdió su teléfono, en su ficha puedes restablecer su verificación en dos pasos.",
        ),
        link=("Ir a Usuarios", "panel:user_list"),
    ),
    Topic(
        key="cuenta",
        icon="lock",
        title="Tu cuenta y tu seguridad",
        summary="Para todo el equipo.",
        steps=(
            "En Mi cuenta guarda tu nombre y tu correo: ahí llegan los avisos.",
            "Activa la verificación en dos pasos con una app de códigos en tu teléfono.",
            "Guarda tus códigos de respaldo en papel, lejos del teléfono.",
            "Si ves un ingreso que no reconoces, cierra las demás sesiones y cambia tu contraseña.",
        ),
        tips=(
            "Nunca te pediremos tu contraseña ni tus códigos por correo o WhatsApp.",
            "En una computadora compartida, cierra sesión al terminar.",
        ),
        link=("Ir a Mi cuenta", "panel:account"),
    ),
)


def topics_for(user):
    return [topic for topic in TOPICS if not topic.permission or user.has_perm(topic.permission)]


@panel_required()
@require_GET
def guide(request):
    topics = [
        {"topic": topic, "url": reverse(topic.link[1]) if topic.link else ""}
        for topic in topics_for(request.user)
    ]
    return panel_render(
        request,
        "panel/guide.html",
        {"topics": topics},
        active="guide",
        title="Guía rápida",
        subtitle="Cómo hacer cada tarea del panel, paso a paso.",
    )
