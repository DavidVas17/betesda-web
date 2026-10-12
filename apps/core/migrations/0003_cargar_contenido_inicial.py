"""Carga en la base de datos el contenido institucional que antes estaba en el código.

Los textos se copian aquí, congelados, para que esta migración no cambie si mañana cambia
``apps/core/content.py``. Solo agrega lo que falta: no pisa nada que el equipo ya haya editado.
"""

from django.db import migrations

MINISTRIES = [
    ("Ministerio Infantil", "Niños", "infantil", "baby",
     "Enseñanza de la Palabra de Dios de manera comprensible, dinámica y amorosa."),
    ("Ministerio de Jóvenes", "Jóvenes", "jovenes", "sparkles",
     "Acompañamiento, discipulado y capacitación para que los jóvenes desarrollen sus dones."),
    ("Ministerio de Adultos", "Adultos", "adultos", "users",
     "Fortalecimiento de la vida espiritual, familiar y comunitaria, "
     "promoviendo el compañerismo y el servicio."),
    ("Ministerio de Adultos Mayores", "Adultos mayores", "adultos-mayores", "hand-heart",
     "Acompañamiento, respeto, cuidado y oportunidades de participación."),
    ("Evangelismo y Misiones", "Compartir la fe", "evangelismo", "globe",
     "Acercamiento a las personas e iniciativas que llevan el mensaje de Cristo "
     "a la comunidad y más allá."),
    ("Acción Social y Servicio Comunitario", "Servir", "accion-social", "helping",
     "Identificación y atención organizada de las necesidades de nuestro entorno."),
    ("Discipulado y Formación", "Crecer", "discipulado", "book",
     "Capacitación de los creyentes en la Palabra de Dios, liderazgo, servicio y vida cristiana."),
]

VALUES = [
    ("Fe", "Confiamos en Dios y en Su Palabra, viviendo cada día conforme a la fe en Jesucristo."),
    ("Amor", "Amamos a Dios y al prójimo con compasión y disposición para servir."),
    ("Unidad", "Promovemos la armonía, el respeto, la reconciliación y el apoyo mutuo."),
    ("Servicio", "Ponemos nuestros dones, tiempo y capacidades al servicio de los demás."),
    ("Evangelismo", "Compartimos el mensaje de Jesucristo, llevando esperanza a la comunidad."),
    ("Trabajo en equipo", "Reconocemos el valor y los dones de cada persona."),
    ("Familia", "Fortalecemos los hogares con amor, respeto y perdón."),
    ("Compromiso", "Servimos con responsabilidad, perseverancia, disposición y excelencia."),
    ("Compasión", "Atendemos con sensibilidad y generosidad las necesidades de las personas."),
    ("Integridad", "Buscamos coherencia entre nuestras palabras, decisiones y acciones."),
]

TEXTS = {
    "mission": (
        "Predicar el evangelio de Jesucristo, formando discípulos mediante la enseñanza de "
        "la Palabra de Dios, el amor, la unidad y el trabajo en equipo; sirviendo integralmente "
        "a niños, jóvenes, adultos y adultos mayores, y llevando esperanza, orientación "
        "y ayuda a la comunidad."
    ),
    "vision": (
        "Ser una iglesia que transforma vidas por medio del amor de Cristo, formando familias "
        "y generaciones comprometidas con Dios, unidas en la fe y dispuestas a servir "
        "y transformar positivamente a la comunidad."
    ),
    "purpose": (
        "Glorificar a Dios y extender Su Reino llevando el amor de Cristo a las personas, "
        "formando discípulos y sirviendo a la comunidad para contribuir a la transformación "
        "espiritual, familiar y social del entorno."
    ),
    "history": (
        "Ministerios Pentecostés Betesda Rosa de Sarón fue fundada en 2006 y ha mantenido "
        "un funcionamiento ininterrumpido desde entonces. A través de sus diferentes "
        "ministerios, la congregación acompaña a niños, jóvenes, adultos y adultos mayores, "
        "y desarrolla su labor de evangelismo, formación cristiana, acción social "
        "y servicio comunitario."
    ),
}


def load(apps, schema_editor):
    Ministry = apps.get_model("core", "Ministry")
    ChurchValue = apps.get_model("core", "ChurchValue")
    SiteConfiguration = apps.get_model("core", "SiteConfiguration")
    for order, (name, tag, slug, icon, description) in enumerate(MINISTRIES, start=1):
        Ministry.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "tag": tag,
                "icon": icon,
                "description": description,
                "order": order * 10,
            },
        )
    if not ChurchValue.objects.exists():
        ChurchValue.objects.bulk_create(
            ChurchValue(name=name, description=description, order=order * 10)
            for order, (name, description) in enumerate(VALUES, start=1)
        )
    for configuration in SiteConfiguration.objects.all():
        changed = [field for field, text in TEXTS.items() if not getattr(configuration, field)]
        for field in changed:
            setattr(configuration, field, TEXTS[field])
        if changed:
            configuration.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("core", "0002_contenido_institucional")]

    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
