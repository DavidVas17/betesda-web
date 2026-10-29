# Seguridad operativa

## Controles incluidos

- contraseñas con los algoritmos seguros de Django;
- sesiones y CSRF administrados por el framework;
- cookies seguras, HSTS y redireccion HTTPS en producción;
- base de datos aislada de la red pública de Docker;
- proceso de aplicación ejecutado sin privilegios;
- mensajes de error sin detalles tecnicos en producción;
- comprobaciones de disponibilidad separadas;
- secretos exclusivamente mediante variables de entorno;
- deteccion de llaves privadas antes del commit;
- `.env` excluido de Git: cada ambiente crea el suyo desde `.env.example`;
- administración técnica (`DJANGO_ADMIN_URL`) solo para el superusuario;
- límite de mensajes por visitante en el formulario público (`CONTACT_RATE_LIMIT_*`);
- IP real del visitante detrás de Caddy (`DJANGO_TRUST_X_FORWARDED_FOR`);
- freno a quien prueba contraseñas en el panel y en la administración técnica: 5 fallos por
  usuario e IP, o 20 por IP, bloquean 15 minutos (`LOGIN_RATE_LIMIT_*`). El bloqueo es por
  usuario **e** IP, así nadie puede dejar fuera a otra persona desde su conexión. El
  superusuario puede desbloquear a alguien borrando sus "intentos fallidos de ingreso" en la
  administración técnica;
- recuperación de contraseña por correo solo para cuentas activas del equipo, con enlace de un
  solo uso que vence a las 2 horas (`PASSWORD_RESET_TIMEOUT`) y el mismo freno de intentos. La
  respuesta es idéntica exista o no la cuenta;
- política de contenido (CSP) estricta: solo scripts, estilos, fuentes e imágenes del propio
  sitio, sin código en línea; la única excepción es el mapa de Google. Las plantillas nunca
  deben llevar `<script>` sin `src`, `style="…"` ni `onclick`; una prueba lo vigila. Para
  probar un cambio sin bloquear, `DJANGO_CSP_REPORT_ONLY=true` (es lo predeterminado en
  desarrollo);
- `Permissions-Policy` que apaga cámara, micrófono, ubicación, pagos y USB;
- los archivos subidos se sirven con una CSP que impide ejecutarlos como página;
- las fotos se guardan sin metadatos: al subirlas se quita el EXIF (ubicación GPS, fecha,
  modelo del teléfono) y se aplica la orientación. `strip_image_metadata` limpia las que se
  subieron antes; corre en cada despliegue y no toca las que ya están limpias;
- la sesión del panel se cierra tras 8 horas sin actividad (`PANEL_SESSION_HOURS`);
- avisos de seguridad por correo (`apps/accounts/alerts.py`), sin contraseñas ni contenido
  de mensajes:

  | Evento | Quién recibe el aviso |
  | --- | --- |
  | Ingreso bloqueado por intentos fallidos | la persona dueña de la cuenta y quienes administran |
  | Muchos usuarios probados desde una conexión | quienes administran |
  | Inicio de sesión desde un navegador nuevo | la persona (el primer ingreso no avisa) |
  | Contraseña cambiada | la persona |
  | Cuenta nueva en el panel | quienes administran, menos quien la creó |
  | Rol de Administración de la iglesia o superusuario otorgado | la persona y quienes administran |

  "Quienes administran" son los superusuarios, Administración de la iglesia y los correos de
  `SECURITY_ALERT_EMAILS`. El navegador se reconoce con una cookie aleatoria; en la base solo
  se guarda su huella, y los que no se usan en un año se olvidan;
- vulnerabilidades en dependencias: el CI corre `pip-audit` sobre las versiones exactas de
  `uv.lock` en cada PR y cada lunes, y Dependabot abre PRs con las actualizaciones de Python,
  Docker y GitHub Actions. Un PR de seguridad de Dependabot se revisa y se mezcla primero.

## Verificación en dos pasos (2FA)

- Con una app de códigos (Google Authenticator, Microsoft Authenticator, Authy). Se implementa
  con TOTP (RFC 6238) en `apps/accounts/totp.py`, sin dependencias externas; el QR se dibuja en
  el navegador con una copia local de *qrcode-generator* (MIT), así el secreto no sale del sitio.
- **Obligatoria** para el superusuario y Administración de la iglesia (`TWO_FACTOR_ENFORCE`):
  hasta activarla no pueden usar el panel ni el admin. **Opcional** para el resto; el tablero
  la sugiere.
- El admin ya no tiene formulario de ingreso propio: se entra por el panel, con el mismo freno
  de intentos y la misma verificación.
- La contraseña correcta no abre la sesión: queda pendiente 5 minutos hasta escribir el código.
  Cada código sirve una sola vez; 5 códigos malos bloquean 15 minutos y avisan por correo a la
  persona (alguien conoce su contraseña).
- 10 códigos de respaldo de un solo uso, guardados solo como huella SHA-256. Usar uno avisa
  por correo. Se pueden regenerar desde "Mi cuenta".
- Desactivarla o cambiar de teléfono pide contraseña y un código.
- Teléfono perdido: quien gestiona al equipo la restablece desde la ficha de la persona
  ("Restablecer verificación en dos pasos"); si es el superusuario, en el servidor:
  `python manage.py reset_two_factor <usuario>`.

## Formulario de contacto: bots y spam

Las defensas están en `apps/contacts/spam.py`:

| Defensa | Qué hace |
| --- | --- |
| Campo trampa | Un campo invisible que solo llenan los bots |
| Trampa de tiempo | Hora firmada en el formulario; enviar en menos de 3 s o sin firma = bot (`CONTACT_MIN_SECONDS`) |
| Cloudflare Turnstile | Opcional y gratuito: `TURNSTILE_SITE_KEY` y `TURNSTILE_SECRET_KEY` |
| Límite por IP y por correo | `CONTACT_RATE_LIMIT_*` y `CONTACT_EMAIL_RATE_LIMIT_*` |
| Duplicados | El mismo mensaje del mismo correo en 24 h se guarda una vez |
| Contenido | Muchos enlaces, palabras de spam u otro alfabeto → "No deseado", sin aviso al equipo |

A un bot se le responde igual que a una persona, para que no aprenda a esquivar las trampas.
Lo marcado como "No deseado" se conserva 30 días por si fue un error.

## Acciones delicadas, bitácora y errores

- Exportar o borrar mensajes y crear, editar, borrar o restablecer cuentas del equipo piden la
  contraseña otra vez (y el código 2FA si está activa) si se escribió hace más de
  `RECENT_AUTH_MINUTES` (10). Exportar avisa por correo a quienes administran y queda en la
  bitácora.
- La bitácora (Actividad) registra inicios y cierres de sesión con navegador e IP, y muestra los
  intentos fallidos de la última semana: de ingreso, de código 2FA, de recuperación y de
  confirmación.
- En producción, los errores 500 llegan por correo a `ERROR_EMAILS` (o a
  `SECURITY_ALERT_EMAILS`). El reporte omite contraseñas, cookies y los campos del formulario
  de contacto y de las notas internas (`sensitive_post_parameters`).
- El CI escanea la imagen de Docker con Trivy: una vulnerabilidad crítica con arreglo disponible
  detiene el PR.

## Otras protecciones

- Contraseñas de 10 caracteres como mínimo, además de los validadores de Django.
- "Mi cuenta" muestra dónde se ha ingresado y permite cerrar la sesión en los demás dispositivos.
- `/.well-known/security.txt` (RFC 9116) con el contacto de `SECURITY_CONTACT_EMAIL`.
- `robots.txt` excluye el panel sin mencionar la ruta del admin, y el panel responde con
  `X-Robots-Tag: noindex`.
- `Cross-Origin-Resource-Policy: same-origin`: otros sitios no pueden incrustar nuestros archivos.

## Si un secreto llegó a Git

Borrar el archivo del repositorio no basta: queda en el historial. Hay que cambiar el secreto.

1. Generar una `DJANGO_SECRET_KEY` nueva y reemplazarla en el `.env` del servidor.
2. Cambiar la contraseña del superusuario: nuevo valor en `.env` y
   `docker compose exec web python manage.py bootstrap_admin --reset-password`.
3. Cambiar `POSTGRES_PASSWORD` y `DATABASE_URL` si el archivo expuesto los tenía.
4. Reiniciar los servicios y cerrar sesiones abiertas.

## Reglas de administración

- Cada administrador debe tener una cuenta individual.
- No compartir contraseñas por chat ni incluirlas en capturas.
- Otorgar solo los permisos necesarios para el rol.
- Desactivar inmediatamente cuentas que ya no correspondan.
- Revisar usuarios y permisos antes de cada entrega.

## Datos personales

Los formularios deben solicitar solo datos necesarios y mostrar un aviso de privacidad. Los mensajes de contacto no deben aparecer en logs, correos de prueba ni datos de demostracion.

### Plazo de conservación

Las peticiones de oración pueden contener datos muy sensibles, así que no se guardan para
siempre (`apps/contacts/retention.py`):

| Qué | Se elimina | Variable |
| --- | --- | --- |
| Mensajes **cerrados** | 365 días después de su último cambio | `MESSAGE_RETENTION_DAYS` |
| Mensajes **no deseados** | 30 días después | `SPAM_RETENTION_DAYS` |
| **IP** de cada envío | a los 90 días (el mensaje se conserva) | `IP_RETENTION_DAYS` |
| Intentos fallidos de ingreso | al día siguiente | — |

Los mensajes nuevos o en seguimiento nunca se eliminan solos. La página de contacto avisa del
plazo y el detalle de cada solicitud cerrada muestra la fecha en que se eliminará. Confirmar los
plazos con la iglesia antes de publicar. En producción el servicio `maintenance` corre la
limpieza cada día; a mano: `make purge ARGS=--dry-run` para ver qué se borraría y `make purge`
para hacerlo.

## Reporte de vulnerabilidades

No abrir una incidencia pública con credenciales o instrucciones explotables. Comunicar el hallazgo al Project Manager y al responsable Backend, revocar los secretos comprometidos y registrar después una descripción saneada del cambio.
