from django.core.exceptions import ValidationError
from django.db import models

from .utils import unique_slug


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        abstract = True


class SiteConfiguration(TimeStampedModel):
    institution_name = models.CharField("nombre de la institucion", max_length=180)
    slogan = models.CharField("lema", max_length=255, blank=True)
    phone = models.CharField("telefono", max_length=30, blank=True)
    email = models.EmailField("correo electronico", blank=True)
    address = models.CharField("direccion", max_length=255, blank=True)
    facebook_url = models.URLField("Facebook", blank=True)
    map_url = models.URLField("mapa", blank=True)
    mission = models.TextField("misión", blank=True)
    vision = models.TextField("visión", blank=True)
    purpose = models.TextField("propósito", blank=True)
    history = models.TextField("historia", blank=True)

    class Meta:
        verbose_name = "configuracion del sitio"
        verbose_name_plural = "configuracion del sitio"

    def __str__(self) -> str:
        return self.institution_name

    def clean(self) -> None:
        if not self.pk and SiteConfiguration.objects.exists():
            raise ValidationError("Solo puede existir una configuracion general del sitio.")


class Ministry(TimeStampedModel):
    class Icon(models.TextChoices):
        BABY = "baby", "Niños"
        SPARKLES = "sparkles", "Jóvenes"
        USERS = "users", "Grupo de personas"
        HAND_HEART = "hand-heart", "Mano con corazón"
        GLOBE = "globe", "Mundo"
        HELPING = "helping", "Manos que ayudan"
        BOOK = "book", "Libro abierto"
        CHURCH = "church", "Iglesia"
        HEART = "heart", "Corazón"
        PRAYER = "prayer", "Oración"
        CALENDAR = "calendar", "Calendario"
        CAMERA = "camera", "Cámara"

    name = models.CharField("nombre", max_length=120)
    tag = models.CharField("etiqueta corta", max_length=40)
    slug = models.SlugField("identificador", max_length=140, unique=True, blank=True)
    icon = models.CharField("ícono", max_length=20, choices=Icon.choices, default=Icon.CHURCH)
    description = models.CharField("descripción", max_length=300)
    order = models.PositiveSmallIntegerField("orden", default=0)
    is_active = models.BooleanField("mostrar en el sitio", default=True)

    class Meta:
        ordering = ("order", "name")
        verbose_name = "ministerio"
        verbose_name_plural = "ministerios"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)


class ChurchValue(TimeStampedModel):
    name = models.CharField("valor", max_length=80)
    description = models.CharField("descripción", max_length=300)
    order = models.PositiveSmallIntegerField("orden", default=0)
    is_active = models.BooleanField("mostrar en el sitio", default=True)

    class Meta:
        ordering = ("order", "name")
        verbose_name = "valor"
        verbose_name_plural = "valores"

    def __str__(self) -> str:
        return self.name
