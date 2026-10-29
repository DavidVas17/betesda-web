from datetime import timedelta

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ContactMessage(TimeStampedModel):
    class Kind(models.TextChoices):
        CONTACT = "CONTACT", "Contacto"
        PRAYER = "PRAYER", "Petición de oración"

    class Status(models.TextChoices):
        NEW = "NEW", "Nuevo"
        IN_PROGRESS = "IN_PROGRESS", "En seguimiento"
        CLOSED = "CLOSED", "Cerrado"
        SPAM = "SPAM", "No deseado"

    name = models.CharField("nombre", max_length=120)
    kind = models.CharField(
        "tipo de solicitud",
        max_length=10,
        choices=Kind.choices,
        default=Kind.CONTACT,
        db_index=True,
    )
    email = models.EmailField("correo electronico")
    phone = models.CharField("teléfono", max_length=30, blank=True)
    subject = models.CharField("asunto", max_length=180)
    message = models.TextField("mensaje")
    status = models.CharField(
        "estado", max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    privacy_accepted = models.BooleanField("acepto aviso de privacidad", default=False)
    source_ip = models.GenericIPAddressField("direccion IP", null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_contact_messages",
    )
    internal_notes = models.TextField("notas internas", blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "created_at"), name="contact_status_date_idx")]
        verbose_name = "mensaje de contacto"
        verbose_name_plural = "mensajes de contacto"
        permissions = [("export_contactmessage", "Puede exportar mensajes de contacto")]

    def __str__(self) -> str:
        return f"{self.subject} - {self.name}"

    @property
    def scheduled_deletion(self):
        """Fecha en que se eliminará solo (ver ``apps.contacts.retention``), o ``None``."""
        days = {
            self.Status.CLOSED: settings.MESSAGE_RETENTION_DAYS,
            self.Status.SPAM: settings.SPAM_RETENTION_DAYS,
        }.get(self.status)
        if days is None or self.updated_at is None:
            return None
        return self.updated_at + timedelta(days=days)


class MessageReply(models.Model):
    """Respuesta enviada desde el panel con el correo de la iglesia. Se borra junto con la
    solicitud cuando cumple su plazo de conservación."""

    message = models.ForeignKey(
        ContactMessage, verbose_name="solicitud", on_delete=models.CASCADE, related_name="replies"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="enviada por",
        null=True,
        on_delete=models.SET_NULL,
        related_name="message_replies",
    )
    subject = models.CharField("asunto", max_length=200)
    body = models.TextField("mensaje")
    sent_at = models.DateTimeField("enviada", auto_now_add=True)

    class Meta:
        ordering = ("-sent_at",)
        verbose_name = "respuesta enviada"
        verbose_name_plural = "respuestas enviadas"

    def __str__(self) -> str:
        return f"Respuesta a #{self.message_id}"
