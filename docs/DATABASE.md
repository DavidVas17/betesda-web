# Base de datos, migraciones y respaldos

## Persistencia

PostgreSQL conserva su información en el volumen `postgres_data`. `docker compose down` no elimina los datos. No use `docker compose down -v` salvo que se pretenda borrar completamente el ambiente local.

## Respaldo

```bash
make backup        # base de datos
make backup-media  # fotos e imágenes subidas (no están en la base de datos)
```

Los comandos generan archivos fechados en `backups/`. Un respaldo completo son los dos archivos. Esa carpeta no debe confirmarse en Git. Copie los respaldos de producción a una ubicación cifrada y separada del servidor.

## Restauracion controlada

1. Confirmar el ambiente y el archivo exacto.
2. Crear un respaldo previo del estado actual.
3. Detener escrituras de la aplicación.
4. Restaurar con `pg_restore` en una base vacia o temporal.
5. Ejecutar pruebas de integridad y flujos principales.
6. Documentar fecha, responsable y resultado.

Después de verificar en una base temporal, la restauración en el ambiente real se hace con:

```bash
make restore FILE=backups/betesda-AAAAMMDD-HHMMSS.dump CONFIRMAR=si
make restore-media FILE=backups/media-AAAAMMDD-HHMMSS.tar.gz CONFIRMAR=si
```

Son operaciones destructivas: sin `CONFIRMAR=si` el comando se detiene y no toca nada.

## Politica sugerida de producción

- respaldo diario;
- retención de 7 copias diarias y 4 semanales;
- prueba de restauración mensual;
- respaldo adicional antes de migraciones de riesgo;
- acceso limitado al responsable de infraestructura y su sustituto autorizado.

