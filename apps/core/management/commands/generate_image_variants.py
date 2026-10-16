from django.core.management.base import BaseCommand

from apps.events.models import Event
from apps.gallery.models import Photo
from apps.news.models import Post


class Command(BaseCommand):
    help = (
        "Crea las versiones WebP reducidas de las imágenes que ya existían. "
        "Usa --todas para regenerarlas aunque ya existan."
    )

    def add_arguments(self, parser):
        parser.add_argument("--todas", action="store_true", help="Regenera todas las versiones.")

    def handle(self, *args, **options):
        force = options["todas"]
        total = 0
        for model in (Event, Post, Photo):
            for item in model.objects.iterator():
                changed = item.refresh_image_variants(force=force)
                if changed:
                    model.objects.filter(pk=item.pk).update(
                        **{name: getattr(item, name).name or "" for name in changed}
                    )
                    total += 1
        self.stdout.write(self.style.SUCCESS(f"Imágenes optimizadas: {total}"))
