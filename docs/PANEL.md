# BackOffice de la iglesia

Abra **http://localhost:8000/panel/** e ingrese con su cuenta actual. El panel tiene una interfaz
propia, independiente de las pantallas del administrador de Django. Ambos usan los mismos modelos,
la misma base de datos, los mismos archivos y las mismas cuentas. No es necesario copiar datos ni
ejecutar migraciones para habilitarlo.

## Navegación

- **Inicio:** solicitudes pendientes, próximos eventos publicados, noticias, álbumes y acciones
  rápidas según los permisos de la cuenta.
- **Eventos:** buscar, crear, editar, destacar, publicar, retirar o duplicar como borrador. Las
  fechas se capturan en la zona horaria configurada del proyecto.
- **Noticias:** crear borradores, editar textos e imágenes, publicar, programar con una fecha
  futura o archivar. La autoría se asigna a la cuenta que crea la noticia.
- **Galería:** organizar álbumes y cargar hasta 30 fotografías a la vez, con un máximo de 8 MB
  por imagen. Cada fotografía admite descripción alternativa, pie de foto y orden.
- **Mensajes:** recibir los contactos y peticiones de oración enviados desde el sitio. Filtrar
  por texto, tipo o estado; abrir la solicitud; asignar responsable; registrar notas internas;
  marcar seguimiento, cerrar o reabrir. Los datos originales de la persona se conservan.
  Los botones de correo y teléfono abren la aplicación correspondiente del equipo; el panel no
  envía correos automáticamente. La exportación CSV respeta los filtros de la bandeja.
- **Configuración:** actualizar nombre, lema, teléfono, correo, dirección, Facebook y Google Maps.
  Los cambios se reflejan directamente en el sitio público.
- **Mi cuenta:** editar los datos propios y cambiar la contraseña conservando la sesión actual.
- **Usuarios:** disponible para la cuenta principal; crear colaboradores, cambiar sus datos,
  desactivar acceso y restablecer contraseñas. Las cuentas principales se protegen de estas
  operaciones. Una cuenta autora de noticias debe desactivarse antes que eliminarse.
- **Actividad:** historial de cambios del equipo, disponible para la cuenta principal.

## Acceso y protección

Solo entran cuentas activas con acceso de equipo (`is_staff`). Tras varios intentos fallidos el
ingreso se bloquea unos minutos, y quien olvidó su contraseña la recupera desde "¿Olvidaste tu
contraseña?" con el correo guardado en su cuenta. Lo que cada persona puede hacer lo
deciden sus roles, que se combinan; la matriz completa está en [ROLES.md](ROLES.md). Cada operación
comprueba los permisos en el servidor, y ningún formulario del panel puede crear un superusuario.

Las operaciones que cambian datos requieren POST y protección CSRF. Las eliminaciones muestran
primero una confirmación. Los formularios validan los datos y las imágenes en el servidor. Las
pantallas privadas no se almacenan en caché, los textos se escapan al mostrarlos y las exportaciones
protegen los valores que una hoja de cálculo podría interpretar como fórmulas.

El diseño se adapta a computadora, tableta y teléfono. En pantallas pequeñas el botón de menú abre
la navegación; también puede cerrarse con Escape. Los formularios y enlaces principales funcionan
sin JavaScript.

La administración técnica (**/admin/**, o la ruta de `DJANGO_ADMIN_URL`) es exclusiva del
superusuario. Las cuentas del equipo que intenten entrar son enviadas al inicio de sesión del admin.

## Validación local

```bash
docker compose exec -T web python manage.py check
docker compose exec -T web ruff check apps/backoffice/panel tests/test_panel_access.py tests/test_panel_accounts.py tests/test_panel_content.py tests/test_panel_messages.py
docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest
```
