from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ContactMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado")),
                ("name", models.CharField(max_length=120, verbose_name="nombre")),
                ("email", models.EmailField(max_length=254, verbose_name="correo electronico")),
                ("subject", models.CharField(max_length=180, verbose_name="asunto")),
                ("message", models.TextField(verbose_name="mensaje")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("NEW", "Nuevo"),
                            ("IN_PROGRESS", "En seguimiento"),
                            ("CLOSED", "Cerrado"),
                            ("SPAM", "No deseado"),
                        ],
                        db_index=True,
                        default="NEW",
                        max_length=20,
                        verbose_name="estado",
                    ),
                ),
                ("privacy_accepted", models.BooleanField(default=False, verbose_name="acepto aviso de privacidad")),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True, verbose_name="direccion IP")),
            ],
            options={
                "verbose_name": "mensaje de contacto",
                "verbose_name_plural": "mensajes de contacto",
                "ordering": ("-created_at",),
                "indexes": [models.Index(fields=["status", "created_at"], name="contact_status_date_idx")],
            },
        )
    ]

