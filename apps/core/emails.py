"""Correos del sitio con la identidad Carbón y oro.

Cada correo se arma con las mismas piezas (título, párrafos, detalles, botón, nota) y sale
en dos versiones: HTML con diseño y texto plano para los clientes que no muestran HTML. Así
el contenido nunca difiere entre las dos.

La plantilla usa tablas y estilos en línea porque es lo único que respetan Gmail, Outlook y
las apps de correo; no carga imágenes externas, así se ve completa aunque el cliente las
bloquee.
"""

import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.formats import date_format

logger = logging.getLogger(__name__)


def now_label() -> str:
    """Fecha y hora de Guatemala, por ejemplo «28 de octubre de 2026, 14:49»."""
    return date_format(timezone.localtime(), "j \\d\\e F \\d\\e Y, H:i")


@dataclass
class Email:
    subject: str
    title: str
    paragraphs: list[str] = field(default_factory=list)
    details: list[tuple[str, str]] = field(default_factory=list)
    button: tuple[str, str] | None = None  # (texto, enlace)
    note: str = ""  # aviso destacado, por ejemplo "Si no fuiste tú…"
    footer: str = ""
    eyebrow: str = "Betesda Rosa de Sarón"
    tone: str = "default"  # "default" o "alert" (franja de alerta)
    preheader: str = ""  # texto de vista previa en la bandeja

    def text(self) -> str:
        lines = [self.title, ""]
        lines += [p for paragraph in self.paragraphs for p in (paragraph, "")]
        if self.details:
            lines += [f"{label}: {value}" for label, value in self.details] + [""]
        if self.button:
            lines += [f"{self.button[0]}:", self.button[1], ""]
        if self.note:
            lines += [self.note, ""]
        lines += ["—", self.footer or "Betesda Rosa de Sarón · Villa Nueva, Guatemala"]
        return "\n".join(lines).strip() + "\n"

    def html(self) -> str:
        return render_to_string(
            "emails/base.html",
            {
                "email": self,
                "preheader": self.preheader or (self.paragraphs[0] if self.paragraphs else ""),
            },
        )

    def message(self, *, to=(), bcc=()) -> EmailMultiAlternatives:
        message = EmailMultiAlternatives(
            subject=self.subject,
            body=self.text(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=list(to),
            bcc=list(bcc),
        )
        message.attach_alternative(self.html(), "text/html")
        return message
