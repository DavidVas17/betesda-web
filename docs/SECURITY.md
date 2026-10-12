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
- IP real del visitante detrás de Caddy (`DJANGO_TRUST_X_FORWARDED_FOR`).

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

Los formularios deben solicitar solo datos necesarios y mostrar un aviso de privacidad. Los mensajes de contacto no deben aparecer en logs, correos de prueba ni datos de demostracion. Definir con la institución un periodo de retención antes de publicar el formulario.

## Reporte de vulnerabilidades

No abrir una incidencia pública con credenciales o instrucciones explotables. Comunicar el hallazgo al Project Manager y al responsable Backend, revocar los secretos comprometidos y registrar después una descripción saneada del cambio.
