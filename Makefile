.DEFAULT_GOAL := help

.PHONY: help setup up down logs shell migrate migrations test lint format check admin roles backup restore prod-up

help:
	@awk 'BEGIN {FS = ":.*##"; printf "\nComandos disponibles:\n"} /^[a-zA-Z_-]+:.*?##/ {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Prepara el entorno local por primera vez
	@test -f .env || cp .env.example .env
	docker compose up --build -d

up: ## Inicia la aplicacion y PostgreSQL
	docker compose up --build -d

down: ## Detiene los contenedores
	docker compose down

logs: ## Muestra los logs de la aplicacion
	docker compose logs -f web

shell: ## Abre una terminal dentro de la aplicacion
	docker compose exec web sh

migrate: ## Aplica migraciones
	docker compose exec web python manage.py migrate

migrations: ## Genera migraciones nuevas
	docker compose exec web python manage.py makemigrations

test: ## Ejecuta pruebas y cobertura
	docker compose exec web coverage run -m pytest
	docker compose exec web coverage report

lint: ## Verifica estilo y errores estaticos
	docker compose exec web ruff check .

format: ## Formatea el codigo Python
	docker compose exec web ruff format .
	docker compose exec web ruff check --fix .

check: ## Ejecuta las verificaciones antes de un PR
	docker compose exec web ruff check .
	docker compose exec web ruff format --check .
	docker compose exec web python manage.py check
	docker compose exec web python manage.py makemigrations --check --dry-run
	docker compose exec web pytest

admin: ## Crea o actualiza el administrador definido en .env
	docker compose exec web python manage.py bootstrap_admin

roles: ## Aplica los permisos de cada rol (Administradores / Editores)
	docker compose exec web python manage.py setup_roles

backup: ## Crea un respaldo fechado de PostgreSQL en ./backups
	@mkdir -p backups
	docker compose exec -T db pg_dump -U "$${POSTGRES_USER:-betesda}" -d "$${POSTGRES_DB:-betesda}" -Fc > "backups/betesda-$$(date +%Y%m%d-%H%M%S).dump"

prod-up: ## Inicia la configuracion de produccion
	docker compose -f compose.prod.yaml up --build -d
