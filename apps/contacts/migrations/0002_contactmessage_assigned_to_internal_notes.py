import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contacts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="contactmessage",
            name="assigned_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_contact_messages",
                to=settings.AUTH_USER_MODEL,
                verbose_name="responsable",
            ),
        ),
        migrations.AddField(
            model_name="contactmessage",
            name="internal_notes",
            field=models.TextField(blank=True, verbose_name="notas internas"),
        ),
    ]
