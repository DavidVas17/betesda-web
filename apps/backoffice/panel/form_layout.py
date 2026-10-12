"""Agrupa los campos de un formulario del panel en bloques con título.

Cada formulario declara ``fieldsets`` como tuplas ``(título, descripción, campos)``. Los
campos que el formulario quitó (por ejemplo, los de publicación para Colaboración) se omiten
solos, y los que no aparecen en ningún bloque se muestran al final.
"""


class FieldsetsMixin:
    fieldsets: tuple[tuple[str, str, tuple[str, ...]], ...] = ()

    def fieldset_groups(self):
        if not self.fieldsets:
            return []
        used: set[str] = set()
        groups = []
        for title, description, names in self.fieldsets:
            used.update(names)
            bound = [self[name] for name in names if name in self.fields]
            if bound:
                groups.append({"title": title, "description": description, "fields": bound})
        rest = [self[name] for name in self.fields if name not in used and not self[name].is_hidden]
        if rest:
            groups.append({"title": "Más datos", "description": "", "fields": rest})
        return groups
