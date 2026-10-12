# Roles y permisos

Hay dos niveles de acceso:

- **Superadministrador** (`is_superuser`): el único que entra a la administración técnica
  (`/admin/` o la ruta de `DJANGO_ADMIN_URL`). Se crea con `python manage.py bootstrap_admin`.
  Conviene que existan como máximo dos, y que esas personas usen además una cuenta normal para el
  trabajo diario.
- **Equipo** (`is_staff`): trabaja solo en `/panel/`, con uno o varios roles. Los permisos de
  varios roles se suman. Una cuenta sin roles solo ve su propia cuenta.

Los roles son grupos de Django definidos en código (`apps/accounts/roles.py`). Sus permisos se
reescriben después de cada `migrate` y con `python manage.py setup_roles`, así que no se editan a
mano.

## Matriz

| Acción | Admin. iglesia | Coordinación | Colaboración | Galería | Atención | Solo lectura |
| --- | --- | --- | --- | --- | --- | --- |
| Ver eventos y noticias | Sí | Sí | Sí | No | No | Sí |
| Crear y editar eventos y noticias | Sí | Sí | Solo sus borradores | No | No | No |
| Publicar, retirar o destacar eventos y noticias | Sí | Sí | No | No | No | No |
| Eliminar eventos y noticias | Sí | Sí | No | No | No | No |
| Ver galería | Sí | Sí | Sí | Sí | No | Sí |
| Crear álbumes y subir fotos | Sí | Sí | Solo en sus borradores | Sí | No | No |
| Publicar y eliminar álbumes | Sí | Sí | No | Sí | No | No |
| Ver peticiones de oración y mensajes | Sí | No | No | No | Sí | No |
| Dar seguimiento (estado, responsable, notas) | Sí | No | No | No | Sí | No |
| Exportar mensajes a CSV | Sí | No | No | No | No | No |
| Eliminar mensajes | Sí | No | No | No | No | No |
| Configuración del sitio | Sí | No | No | No | No | No |
| Nuestra iglesia: ministerios y valores | Sí | No | No | No | No | No |
| Gestionar usuarios y sus roles | Sí (ver reglas) | No | No | No | No | No |
| Ver la bitácora de actividad | Sí | No | No | No | No | No |

La prueba `tests/test_roles.py::test_panel_matrix` comprueba esta tabla contra las URL reales.

## Reglas

- **Colaboración** guarda siempre borradores: los campos de publicación no aparecen en su
  formulario y el servidor ignora si se envían. Edita solo lo que creó, y solo mientras no esté
  publicado. Alguien de Coordinación lo revisa y lo publica.
- **Administración de la iglesia** asigna todos los roles menos el suyo; ese rol solo lo asigna o
  quita el superadministrador. Tampoco puede editar, desactivar ni cambiar la contraseña de otra
  persona con su mismo rol.
- Nadie cambia sus propios roles ni desactiva su propia cuenta desde el panel. La contraseña propia
  se cambia en "Mi cuenta", pidiendo la actual.
- Al desactivar una cuenta, sus solicitudes abiertas quedan "Sin asignar". Una solicitud solo se
  puede asignar a alguien que puede leer mensajes.
- Cada cambio de cuenta queda en la bitácora con los roles resultantes.

## Cambiar un rol

Edita `apps/accounts/roles.py`, ejecuta las pruebas y despliega: `migrate` (o `setup_roles`) deja
los grupos exactamente como dice el código. Si agregas un permiso propio nuevo, decláralo en el
`Meta.permissions` del modelo y crea su migración.
