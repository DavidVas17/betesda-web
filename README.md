# Betesda Rosa de Sarón - sitio web institucional

Base técnica del sitio web responsivo de Ministerios Pentecostés Betesda Rosa de Sarón. El proyecto usa un monolito modular para entregar rápido sin sacrificar separación de responsabilidades, seguridad ni capacidad de crecimiento.

## Arquitectura elegida

- **Django 5.2 LTS:** autenticación, permisos, panel administrativo, validación y protecciones web integradas.
- **PostgreSQL 17:** almacenamiento relacional de eventos, noticias, galería, mensajes y configuración.
- **Caddy 2:** proxy inverso, compresión y HTTPS automático en un servidor con dominio público.
- **Docker Compose:** mismo entorno para desarrollo, pruebas y despliegue.
- **uv + Ruff + Pytest:** dependencias bloqueadas, validación rápida y pruebas automatizadas.
- **GitHub Actions:** control de calidad y construcción del contenedor en cada pull request.

La decisión completa está documentada en [docs/adr/0001-monolito-modular.md](docs/adr/0001-monolito-modular.md).

## Requisitos

- Git
- Docker Desktop 4.30 o superior con Docker Compose v2
- Make es opcional; en Windows puede usarse Git Bash, WSL o ejecutar los comandos `docker compose` equivalentes.

No es necesario instalar Python, PostgreSQL ni Django en la computadora.

## Primer inicio

```bash
git clone <URL-DEL-REPOSITORIO>
cd betesda-web
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py bootstrap_admin
```

Antes del último comando, cambie `DJANGO_SUPERUSER_PASSWORD` dentro de `.env`. Luego abra:

- Sitio: <http://localhost:8000>
- Administración: <http://localhost:8000/admin/>
- Estado: <http://localhost:8000/health/ready/>

## Flujo diario

```bash
make up          # iniciar
make logs        # revisar registros
make migrations  # crear migraciones después de cambiar modelos
make migrate     # aplicar migraciones
make test        # ejecutar pruebas
make check       # validar antes de abrir un pull request
make down        # detener
```

## Módulos iniciales

| Módulo | Responsabilidad |
| --- | --- |
| `accounts` | Usuarios, roles, autenticación y permisos |
| `core` | Configuración institucional y salud de la aplicación |
| `events` | Eventos, actividades y contenidos destacados |
| `news` | Noticias, anuncios y flujo borrador/publicación |
| `gallery` | Álbumes, fotografías y textos alternativos |
| `contacts` | Mensajes recibidos y seguimiento administrativo |

## Reglas importantes

1. Nunca confirmar `.env`, contraseñas, respaldos ni datos reales en Git.
2. Toda funcionalidad entra por una rama corta y un pull request.
3. Una migración publicada no se modifica; se crea una nueva.
4. Los archivos cargados no se guardan dentro del repositorio.
5. `main` debe permanecer desplegable y protegida contra pushes directos.

Consulte [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) y [docs/COLLABORATION.md](docs/COLLABORATION.md) antes de comenzar una historia.

La secuencia de trabajo está en [docs/ROADMAP.md](docs/ROADMAP.md) y el procedimiento de publicación en [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Estado del alcance

El sitio incluye una portada con información general y adelantos de contenido, y páginas independientes para **Nosotros**, **Ministerios**, **Eventos**, **Noticias**, **Galería** y **Contacto**, accesibles desde el menú principal. Eventos y noticias tienen páginas de detalle; la galería organiza las fotografías en álbumes con vista ampliada. Solo se muestra contenido publicado, y las noticias con fecha futura permanecen ocultas hasta su publicación.

La página **Peticiones de oración / Contáctanos** contiene dos pestañas con los mismos campos: nombre, correo electrónico, teléfono opcional, asunto, mensaje y consentimiento. Cada pestaña adapta los textos y conserva los datos al cambiar entre ellas. Los envíos válidos se guardan con estado **Nuevo** y su tipo correspondiente; aparecen en **Mensajes nuevos** y pueden filtrarse por tipo en el BackOffice. Incluye validación del servidor, protección CSRF, un campo antispam oculto y un máximo de 5,000 caracteres por mensaje. Las pestañas también funcionan como enlaces con JavaScript desactivado.

La información de la iglesia y el logotipo provienen del documento institucional proporcionado. Las fuentes y decisiones de contenido están en [docs/CONTENT.md](docs/CONTENT.md). Los datos de contacto se actualizan desde **Configuración del sitio**. Al actualizar una instalación existente, aplique las migraciones con `docker compose exec web python manage.py migrate` para agregar el teléfono opcional y el tipo de solicitud.
