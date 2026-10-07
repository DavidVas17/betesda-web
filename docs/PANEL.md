# Panel administrativo (backoffice)

Guía para quien administra el contenido del sitio y para quien da mantenimiento al panel.

## Qué incluye

| Área | Qué hace |
| --- | --- |
| Tablero de inicio | Saludo, accesos rápidos, pendientes con alertas, indicadores, próximos eventos, últimos mensajes, gráfico semanal y avance de la configuración del sitio. Cada bloque aparece solo si la persona tiene permiso para verlo. |
| Aviso en la cabecera | Contador de mensajes de contacto sin atender, visible en todo el panel. |
| Tema | Negro y dorado de la institución, modo claro/oscuro (usa el selector de Django) y adaptable a móvil. |
| Eventos | Miniatura, estado temporal (Próximo, Hoy, En curso, Realizado), filtro por momento, publicar/destacar desde el listado, acciones masivas y duplicar como borrador. Valida que el fin no sea anterior al inicio. |
| Noticias | Autor asignado automáticamente, tiempo de lectura, acciones masivas (publicar, borrador, archivar, destacar). |
| Galería | Miniaturas, conteo de fotos, orden editable y **subida masiva** (arrastrar y soltar hasta 30 fotos de 8 MB) desde el botón «Subir varias fotos» del álbum. |
| Mensajes de contacto | Estado con color, tiempo de espera, responsable, notas internas, responder por correo con un clic, acciones masivas y exportación CSV (solo administradores). |
| Configuración del sitio | Registro único: el menú abre directamente el formulario. |
| Usuarios | Rol con efecto real sobre permisos, activar/desactivar cuentas, y los administradores de rol no ven al superusuario. |
| Bitácora | Historial de solo lectura de quién creó, modificó o eliminó contenido. |

## Roles

Los permisos se definen en `apps/accounts/roles.py` y se aplican con `make roles`
(`python manage.py setup_roles`). El contenedor lo ejecuta en cada arranque, así que
**los permisos de estos dos grupos se restablecen a lo definido en el código**; para cambiarlos,
edite `ROLE_PERMISSIONS` en un pull request.

| Permiso | Administradores | Editores de contenido |
| --- | :---: | :---: |
| Eventos | crear, editar, eliminar | crear, editar |
| Noticias | crear, editar, eliminar | crear, editar |
| Álbumes | crear, editar, eliminar | crear, editar |
| Fotografías | crear, editar, eliminar | crear, editar, eliminar |
| Mensajes de contacto | ver, editar, eliminar | ver, editar |
| Exportar mensajes (CSV) | sí | no |
| Configuración del sitio | ver, editar | no |
| Usuarios | crear, editar | no |
| Bitácora | ver | no |

Al guardar un usuario, el sistema lo coloca en el grupo de su rol y lo retira del otro.
Las cuentas creadas desde el panel quedan con acceso al panel (`is_staff`) automáticamente.

## Agregar un bloque al tablero

1. Agregue la consulta en `apps/backoffice/dashboard.py`, protegida con `user.has_perm(...)`.
2. Muestre el resultado en `apps/backoffice/templates/admin/dashboard.html`.
3. Cubra el caso con una prueba en `tests/test_backoffice.py`.

## Notas

- Los eventos y noticias publicados tienen páginas de detalle y el enlace «Ver en el sitio» disponible desde el panel. Los borradores, noticias archivadas y noticias programadas para una fecha futura no se muestran al público.
- La portada muestra hasta tres próximas actividades y hasta tres noticias; las páginas de Eventos, Noticias y Galería contienen los listados paginados y sus detalles.
- Solo los álbumes publicados aparecen en la galería. Las fotografías conservan el texto alternativo, descripción y orden definidos en el panel.
- Los datos de teléfono, dirección, correo y enlaces configurados se reflejan en Contacto y en el pie de página; cuando faltan, se usan los datos institucionales del documento proporcionado. No se inventa un correo institucional.

## Solicitudes del formulario de contacto

Los visitantes pueden enviar su nombre, correo electrónico, teléfono opcional, asunto y mensaje desde la página **Peticiones de oración / Contáctanos**, aceptando el uso de sus datos para atender la solicitud. No necesitan una cuenta. Cada envío queda clasificado como **Petición de oración** o **Contacto**, con estado **Nuevo**. Ambos tipos cuentan en **Mensajes nuevos** y en el aviso de la cabecera.

El tipo aparece en los mensajes recientes, en el listado y en el detalle. Use el filtro **Tipo de solicitud** para separar peticiones de oración de consultas generales. El teléfono también se muestra en el listado y el detalle, puede buscarse y se incluye en la exportación CSV junto con el tipo de solicitud.

Para atender una solicitud, abra **Mensajes nuevos** en el tablero y seleccione el asunto. Allí encontrará los datos del remitente y la petición, podrá responder por correo, asignar un responsable, agregar notas internas y cambiar el estado a **En seguimiento** o **Cerrado**. Los mensajes y las notas internas no se muestran en el sitio público.
