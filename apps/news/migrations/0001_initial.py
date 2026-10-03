from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Post",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado")),
                ("title", models.CharField(max_length=180, verbose_name="titulo")),
                ("slug", models.SlugField(blank=True, max_length=200, unique=True, verbose_name="identificador")),
                ("excerpt", models.CharField(max_length=280, verbose_name="extracto")),
                ("body", models.TextField(verbose_name="contenido")),
                ("cover_image", models.ImageField(blank=True, upload_to="news/%Y/%m/", verbose_name="imagen")),
                (
                    "status",
                    models.CharField(
                        choices=[("DRAFT", "Borrador"), ("PUBLISHED", "Publicado"), ("ARCHIVED", "Archivado")],
                        db_index=True,
                        default="DRAFT",
                        max_length=12,
                        verbose_name="estado",
                    ),
                ),
                ("published_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="fecha de publicacion")),
                ("is_featured", models.BooleanField(db_index=True, default=False, verbose_name="destacado")),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="posts",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="autor",
                    ),
                ),
            ],
            options={
                "verbose_name": "noticia o anuncio",
                "verbose_name_plural": "noticias y anuncios",
                "ordering": ("-published_at", "-created_at"),
                "indexes": [models.Index(fields=["status", "published_at"], name="news_status_date_idx")],
            },
        )
    ]

