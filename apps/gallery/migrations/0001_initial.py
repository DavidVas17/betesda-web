from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Album",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado")),
                ("title", models.CharField(max_length=180, verbose_name="titulo")),
                ("slug", models.SlugField(blank=True, max_length=200, unique=True, verbose_name="identificador")),
                ("description", models.TextField(blank=True, verbose_name="descripcion")),
                ("event_date", models.DateField(blank=True, null=True, verbose_name="fecha de la actividad")),
                ("is_published", models.BooleanField(db_index=True, default=False, verbose_name="publicado")),
            ],
            options={
                "verbose_name": "album",
                "verbose_name_plural": "albumes",
                "ordering": ("-event_date", "-created_at"),
            },
        ),
        migrations.CreateModel(
            name="Photo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado")),
                ("image", models.ImageField(upload_to="gallery/%Y/%m/", verbose_name="imagen")),
                ("alt_text", models.CharField(max_length=180, verbose_name="texto alternativo")),
                ("caption", models.CharField(blank=True, max_length=255, verbose_name="descripcion breve")),
                ("order", models.PositiveSmallIntegerField(default=0, verbose_name="orden")),
                (
                    "album",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="gallery.album",
                    ),
                ),
            ],
            options={
                "verbose_name": "fotografia",
                "verbose_name_plural": "fotografias",
                "ordering": ("order", "created_at"),
            },
        ),
    ]

