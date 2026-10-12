from django.conf import settings
from django.db import models

from apps.core.images import ImageVariantsMixin
from apps.core.models import TimeStampedModel
from apps.core.utils import unique_slug


class Album(TimeStampedModel):
    title = models.CharField("titulo", max_length=180)
    slug = models.SlugField("identificador", max_length=200, unique=True, blank=True)
    description = models.TextField("descripcion", blank=True)
    event_date = models.DateField("fecha de la actividad", null=True, blank=True)
    is_published = models.BooleanField("publicado", default=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="created_albums",
    )

    class Meta:
        ordering = ("-event_date", "-created_at")
        verbose_name = "album"
        verbose_name_plural = "albumes"
        permissions = [("publish_album", "Puede publicar y despublicar álbumes")]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        super().save(*args, **kwargs)


class Photo(ImageVariantsMixin, TimeStampedModel):
    image_variants = {"image": (("thumb", 800), ("display", 1800))}

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField("imagen", upload_to="gallery/%Y/%m/")
    thumb = models.ImageField(
        "miniatura", upload_to="gallery/%Y/%m/web/", blank=True, editable=False
    )
    display = models.ImageField(
        "imagen para ver", upload_to="gallery/%Y/%m/web/", blank=True, editable=False
    )
    alt_text = models.CharField("texto alternativo", max_length=180)
    caption = models.CharField("descripcion breve", max_length=255, blank=True)
    order = models.PositiveSmallIntegerField("orden", default=0)

    class Meta:
        ordering = ("order", "created_at")
        verbose_name = "fotografia"
        verbose_name_plural = "fotografias"

    def __str__(self) -> str:
        return f"{self.album}: {self.alt_text}"

    @property
    def thumb_url(self) -> str:
        return self.best_url(self.thumb, self.image)

    @property
    def display_url(self) -> str:
        return self.best_url(self.display, self.image)
