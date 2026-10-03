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

Esta entrega corresponde a los cimientos: infraestructura reproducible, modelos base, panel administrativo, primera vista institucional, seguridad, pruebas y automatización. Los flujos públicos completos de eventos, noticias, galería y formulario de contacto se implementan en iteraciones posteriores sobre esta base.
