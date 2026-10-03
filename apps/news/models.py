from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.utils import unique_slug


class Post(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        PUBLISHED = "PUBLISHED", "Publicado"
        ARCHIVED = "ARCHIVED", "Archivado"

    title = models.CharField("titulo", max_length=180)
    slug = models.SlugField("identificador", max_length=200, unique=True, blank=True)
    excerpt = models.CharField("extracto", max_length=280)
    body = models.TextField("contenido")
    cover_image = models.ImageField("imagen", upload_to="news/%Y/%m/", blank=True)
    status = models.CharField(
        "estado", max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    published_at = models.DateTimeField(
        "fecha de publicacion", null=True, blank=True, db_index=True
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="autor",
        on_delete=models.PROTECT,
        related_name="posts",
    )
    is_featured = models.BooleanField("destacado", default=False, db_index=True)

    class Meta:
        ordering = ("-published_at", "-created_at")
        indexes = [models.Index(fields=("status", "published_at"), name="news_status_date_idx")]
        verbose_name = "noticia o anuncio"
        verbose_name_plural = "noticias y anuncios"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("news:detail", kwargs={"slug": self.slug})
