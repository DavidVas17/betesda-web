"""Versiones reducidas de las imágenes que sube el equipo.

Una foto de celular pesa varios megabytes. El sitio no debe enviarla completa a cada visita:
al guardar, cada imagen genera versiones WebP con un ancho máximo (una para tarjetas y otra
para páginas de detalle o la vista ampliada).

La imagen original se conserva, pero sin metadatos: las fotos de celular guardan en su EXIF la
ubicación GPS exacta, la fecha y el modelo del teléfono, y cualquiera que descargue la foto
podría leerlos (por ejemplo, la casa de un miembro). Al subirla se quitan y se aplica la
orientación, para que la foto no aparezca girada.

Uso en un modelo::

    class Event(ImageVariantsMixin, TimeStampedModel):
        image_variants = {"cover_image": (("cover_card", 960), ("cover_large", 1600))}
"""

import io
import logging
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.db import models
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

WEBP_QUALITY = 80
ORIGINAL_QUALITY = 92
# Claves de ``Image.info`` que llevan datos de la persona o del dispositivo.
METADATA_KEYS = ("exif", "xmp", "XML:com.adobe.xmp", "comment", "Description", "Author")


def has_metadata(image: Image.Image) -> bool:
    info_keys = set(image.info) - {"icc_profile", "dpi", "transparency", "gamma", "duration"}
    return (
        bool(image.getexif())
        or bool(info_keys & set(METADATA_KEYS))
        or bool(getattr(image, "text", None))
    )


def strip_metadata(source) -> ContentFile | None:
    """La misma imagen, en su formato, sin EXIF/GPS ni comentarios. ``None`` si ya está limpia.

    Se conserva el perfil de color para que los tonos no cambien.
    """
    try:
        source.open("rb")
        source.seek(0)
        with Image.open(source) as original:
            image_format = original.format
            if image_format not in ("JPEG", "PNG", "WEBP") or not has_metadata(original):
                return None
            icc_profile = original.info.get("icc_profile")
            image = ImageOps.exif_transpose(original)
            options = {"icc_profile": icc_profile} if icc_profile else {}
            if image_format == "JPEG":
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                options.update(quality=ORIGINAL_QUALITY, optimize=True)
            elif image_format == "WEBP":
                options.update(quality=ORIGINAL_QUALITY)
            else:
                options.update(optimize=True)
            buffer = io.BytesIO()
            image.save(buffer, image_format, **options)
    except (OSError, UnidentifiedImageError, ValueError):
        logger.warning("No se pudo limpiar %s", getattr(source, "name", source))
        return None
    finally:
        source.seek(0)
    return ContentFile(buffer.getvalue(), name=PurePosixPath(source.name).name)


def build_variant(source, max_width: int) -> ContentFile | None:
    """Devuelve la imagen como WebP de ``max_width`` px de ancho como máximo."""
    try:
        source.open("rb")
        source.seek(0)
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            if image.width > max_width:
                height = round(image.height * max_width / image.width)
                image = image.resize((max_width, height), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, "WEBP", quality=WEBP_QUALITY, method=6)
    except (OSError, UnidentifiedImageError, ValueError):
        logger.warning("No se pudo generar la versión de %s", getattr(source, "name", source))
        return None
    stem = PurePosixPath(source.name).stem
    return ContentFile(buffer.getvalue(), name=f"{stem}-{max_width}.webp")


class ImageVariantsMixin(models.Model):
    """Genera y mantiene las versiones reducidas declaradas en ``image_variants``."""

    image_variants: dict[str, tuple[tuple[str, int], ...]] = {}

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        touches_images = update_fields is None or any(
            name in update_fields for name in self.image_variants
        )
        if touches_images:
            changed = self.refresh_image_variants()
            if update_fields is not None and changed:
                kwargs["update_fields"] = {*update_fields, *changed}
        super().save(*args, **kwargs)
        self._remember_image_names()

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._remember_image_names()
        return instance

    def _remember_image_names(self) -> None:
        self._image_names = {name: getattr(self, name).name or "" for name in self.image_variants}

    def _variants_missing(self, source_name: str) -> bool:
        variants = self.image_variants[source_name]
        return any(not getattr(self, variant_name) for variant_name, _ in variants)

    def refresh_image_variants(self, *, force: bool = False) -> list[str]:
        """Actualiza las versiones que lo necesiten y devuelve los campos que cambiaron."""
        changed: list[str] = []
        previous = getattr(self, "_image_names", {})
        for source_name, variants in self.image_variants.items():
            source = getattr(self, source_name)
            current = source.name or ""
            if not current:
                for variant_name, _ in variants:
                    if getattr(self, variant_name):
                        setattr(self, variant_name, None)
                        changed.append(variant_name)
                continue
            outdated = current != previous.get(source_name)
            if not getattr(source, "_committed", True):
                # Archivo recién subido: se guarda sin metadatos.
                clean = strip_metadata(source)
                if clean is not None:
                    setattr(self, source_name, clean)
                    source = getattr(self, source_name)
            if not (force or outdated or self._variants_missing(source_name)):
                continue
            for variant_name, width in variants:
                content = build_variant(source, width)
                if content is None:
                    continue
                getattr(self, variant_name).save(content.name, content, save=False)
                changed.append(variant_name)
        return changed

    @staticmethod
    def best_url(*files) -> str:
        """La URL de la primera imagen disponible: la versión reducida o, si falta, la original."""
        for file in files:
            if file:
                return file.url
        return ""
