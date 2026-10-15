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
- los archivos subidos se sirven con una CSP que impide ejecutarlos como página.

## Si un secreto llegó a Git

Borrar el archivo del repositorio no basta: queda en el historial. Hay que cambiar el secreto.

1. Generar una `DJANGO_SECRET_KEY` nueva y reemplazarla en el `.env` del servidor.
2. Cambiar la contraseña del superusuario (`make admin` con el nuevo valor en `.env`).
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
