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

    def __str__(self) -> str:
        return f"{self.subject} - {self.name}"
