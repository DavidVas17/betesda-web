from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SiteConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado")),
                ("institution_name", models.CharField(max_length=180, verbose_name="nombre de la institucion")),
                ("slogan", models.CharField(blank=True, max_length=255, verbose_name="lema")),
                ("phone", models.CharField(blank=True, max_length=30, verbose_name="telefono")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="correo electronico")),
                ("address", models.CharField(blank=True, max_length=255, verbose_name="direccion")),
                ("facebook_url", models.URLField(blank=True, verbose_name="Facebook")),
                ("map_url", models.URLField(blank=True, verbose_name="mapa")),
            ],
            options={
                "verbose_name": "configuracion del sitio",
                "verbose_name_plural": "configuracion del sitio",
            },
        )
    ]

