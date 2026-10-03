from django.core.exceptions import ValidationError
from django.db import models


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

    class Meta:
        verbose_name = "configuracion del sitio"
        verbose_name_plural = "configuracion del sitio"

    def __str__(self) -> str:
        return self.institution_name

    def clean(self) -> None:
        if not self.pk and SiteConfiguration.objects.exists():
            raise ValidationError("Solo puede existir una configuracion general del sitio.")

