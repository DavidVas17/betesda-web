# Desarrollo local

## Preparación

1. Copiar `.env.example` como `.env`.
2. Cambiar la contraseña administrativa de ejemplo.
3. Ejecutar `docker compose up --build -d`.
4. Verificar `docker compose ps` y abrir `/health/ready/`.
5. Crear el administrador con `make admin`.

## Cambios de modelo

```bash
make migrations
make migrate
make check
```

Revise el archivo generado antes de confirmarlo. Nunca edite una migración que ya fue aplicada en un ambiente compartido.

## Definicion de terminado

Una historia está terminada cuando:

- cumple todos sus criterios de aceptacion;
- incluye validación y permisos del lado del servidor;
- agrega o actualiza pruebas;
- funciona en pantalla móvil y escritorio cuando tiene interfaz;
- no empeora accesibilidad ni tiempo de carga;
- `make check` finaliza correctamente;
- cuenta con revisión de otra persona;
- actualiza documentación o migraciones cuando corresponde.

## Datos de desarrollo

Use datos ficticios. No copie mensajes, correos, telefonos ni fotografías de personas reales sin autorizacion. Los archivos cargados se conservan en el volumen `media_data` y no en Git.

## Windows

Docker Desktop debe usar contenedores Linux. Si `make` no está disponible, ejecute directamente el comando indicado en el `Makefile`, por ejemplo:

```powershell
docker compose exec web pytest
```
