from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel
from apps.core.utils import unique_slug


class Event(TimeStampedModel):
    title = models.CharField("titulo", max_length=180)
    slug = models.SlugField("identificador", max_length=200, unique=True, blank=True)
    summary = models.CharField("resumen", max_length=280)
    description = models.TextField("descripcion")
    starts_at = models.DateTimeField("inicio")
    ends_at = models.DateTimeField("finalizacion", null=True, blank=True)
    location = models.CharField("lugar", max_length=200)
    cover_image = models.ImageField("imagen", upload_to="events/%Y/%m/", blank=True)
    is_published = models.BooleanField("publicado", default=False, db_index=True)
    is_featured = models.BooleanField("destacado", default=False, db_index=True)

    class Meta:
        ordering = ("starts_at",)
        indexes = [models.Index(fields=("is_published", "starts_at"), name="events_pub_start_idx")]
        verbose_name = "evento"
        verbose_name_plural = "eventos"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            raise ValidationError(
                {"ends_at": "La finalización no puede ser anterior al inicio del evento."}
            )

    def get_absolute_url(self) -> str:
        return reverse("events:detail", kwargs={"slug": self.slug})

