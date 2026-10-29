from django.core.management.base import BaseCommand

from apps.core.images import strip_metadata
from apps.events.models import Event
from apps.gallery.models import Photo
from apps.news.models import Post


class Command(BaseCommand):
    help = (
        "Quita la ubicación GPS y demás metadatos de las imágenes originales ya subidas. "
        "Las que ya están limpias no se tocan, así que puede correrse en cada despliegue."
    )

    def handle(self, *args, **options):
        cleaned = 0
        for model in (Event, Post, Photo):
            for name in model.image_variants:
                for item in model.objects.exclude(**{name: ""}).iterator():
                    field = getattr(item, name)
                    if not field or not field.storage.exists(field.name):
                        continue
                    content = strip_metadata(field)
                    field.close()
                    if content is None:
                        continue
                    # Se reemplaza en el mismo lugar para no romper enlaces ni versiones.
                    path = field.name
                    field.storage.delete(path)
                    saved = field.storage.save(path, content)
                    if saved != path:
                        model.objects.filter(pk=item.pk).update(**{name: saved})
                    cleaned += 1
        self.stdout.write(self.style.SUCCESS(f"Imágenes sin metadatos: {cleaned}"))
