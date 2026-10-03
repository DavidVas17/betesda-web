# Despliegue de producción

## Infraestructura mínima

- servidor Linux con 2 vCPU, 2 GB de RAM y 20 GB SSD;
- dominio con registros DNS apuntando al servidor;
- puertos 80 y 443 públicos; SSH restringido;
- Docker Engine y Docker Compose v2;
- ubicación externa y cifrada para respaldos.

Para una primera carga institucional, esta configuración es suficiente. La base de datos no publica ningún puerto hacia Internet.

## Preparación

1. Crear un usuario de despliegue sin acceso root directo.
2. Clonar una etiqueta de versión, no una rama con cambios sin revisar.
3. Crear `.env` con valores de producción.
4. Generar `DJANGO_SECRET_KEY` con al menos 50 caracteres aleatorios.
5. Configurar dominio, hosts permitidos y orígenes CSRF con `https://`.
6. Usar contraseñas distintas para PostgreSQL y el administrador.

Variables críticas:

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=betesdarosadesaron.org,www.betesdarosadesaron.org
DJANGO_CSRF_TRUSTED_ORIGINS=https://betesdarosadesaron.org,https://www.betesdarosadesaron.org
CADDY_DOMAIN=betesdarosadesaron.org, www.betesdarosadesaron.org
SECURE_HSTS_SECONDS=31536000
```

## Primera publicación

```bash
docker compose -f compose.prod.yaml config
docker compose -f compose.prod.yaml build
docker compose -f compose.prod.yaml up -d
docker compose -f compose.prod.yaml ps
docker compose -f compose.prod.yaml exec web python manage.py check --deploy
docker compose -f compose.prod.yaml exec web python manage.py bootstrap_admin
```

Verifique el certificado HTTPS, `/health/ready/`, el inicio de sesión, la carga de estáticos y una operación de lectura/escritura controlada.

## Actualización

1. Crear y verificar un respaldo.
2. Obtener la etiqueta aprobada.
3. Revisar migraciones y notas de versión.
4. Construir la nueva imagen.
5. Ejecutar `docker compose -f compose.prod.yaml up -d`.
6. Validar salud, logs y flujos críticos.

## Reversión

El código se revierte desplegando la etiqueta anterior. No se revierten migraciones de forma automática: si una migración no es compatible hacia atrás, el pull request debe incluir un plan específico de despliegue y recuperación. Ante pérdida o corrupción de datos, seguir `docs/DATABASE.md` y restaurar primero en una base temporal.
