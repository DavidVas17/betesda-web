from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado")),
                ("title", models.CharField(max_length=180, verbose_name="titulo")),
                ("slug", models.SlugField(blank=True, max_length=200, unique=True, verbose_name="identificador")),
                ("summary", models.CharField(max_length=280, verbose_name="resumen")),
                ("description", models.TextField(verbose_name="descripcion")),
                ("starts_at", models.DateTimeField(verbose_name="inicio")),
                ("ends_at", models.DateTimeField(blank=True, null=True, verbose_name="finalizacion")),
                ("location", models.CharField(max_length=200, verbose_name="lugar")),
                ("cover_image", models.ImageField(blank=True, upload_to="events/%Y/%m/", verbose_name="imagen")),
                ("is_published", models.BooleanField(db_index=True, default=False, verbose_name="publicado")),
                ("is_featured", models.BooleanField(db_index=True, default=False, verbose_name="destacado")),
            ],
            options={
                "verbose_name": "evento",
                "verbose_name_plural": "eventos",
                "ordering": ("starts_at",),
                "indexes": [models.Index(fields=["is_published", "starts_at"], name="events_pub_start_idx")],
            },
        )
    ]

