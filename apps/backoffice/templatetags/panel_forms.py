from django import template

register = template.Library()


@register.filter
def fieldset_groups(form):
    """Los bloques del formulario, o una lista vacía si el formulario no los define.

    Así ``panel/fields.html`` sirve igual para formularios con bloques (``FieldsetsMixin``)
    y sin ellos (inicio de sesión, cambio de contraseña), sin depender de que Django
    devuelva vacío ante un atributo que no existe.
    """
    groups = getattr(form, "fieldset_groups", None)
    return groups() if callable(groups) else []
