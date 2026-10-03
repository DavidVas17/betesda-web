from django.utils.text import slugify


def unique_slug(instance, value: str, max_length: int = 200) -> str:
    """Genera un slug que no choque con otros registros del mismo modelo.

    Si ya existe "reunion-de-jovenes" devuelve "reunion-de-jovenes-2", etc.
    Evita el IntegrityError cuando dos registros tienen el mismo titulo.
    """
    base = slugify(value)[:max_length] or "registro"
    queryset = type(instance)._default_manager.all()
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    slug = base
    counter = 2
    while queryset.filter(slug=slug).exists():
        suffix = f"-{counter}"
        slug = f"{base[: max_length - len(suffix)]}{suffix}"
        counter += 1
    return slug
