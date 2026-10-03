# Colaboracion y control de cambios

## Flujo Git

Se usará desarrollo basado en ramas cortas sobre `main`:

1. Crear o asignar una incidencia con requerimiento y criterios de aceptacion.
2. Actualizar `main` y crear una rama.
3. Realizar cambios pequeños y verificables.
4. Ejecutar `make check`.
5. Abrir un pull request y solicitar al menos una revisión.
6. Corregir observaciones y combinar mediante squash.
7. Eliminar la rama después de integrar.

Nombres recomendados:

- `feature/RF-04-eventos`
- `fix/RF-11-validación-contacto`
- `docs/arquitectura-despliegue`
- `chore/actualizar-dependencias`

## Proteccion de `main`

Configurar en GitHub:

- prohibir push directo y eliminacion;
- exigir pull request y una aprobacion;
- exigir los trabajos `quality` y `container`;
- exigir conversaciones resueltas;
- invalidar aprobaciones si cambia el código;
- restringir force push.

## Responsabilidad por frente

| Frente | Responsable primario | Revisor sugerido |
| --- | --- | --- |
| Alcance y criterios | QA / Analista | Project Manager |
| Plantillas y estilos | Frontend / UI | QA / Analista |
| Modelos, permisos y backend | Backend / Database | QA / Analista |
| Migraciones y respaldo | Backend / Database | Project Manager |
| Integracion y entrega | Project Manager | Equipo completo |

La propiedad no impide apoyar otros frentes. Si un cambio toca autenticación, migraciones o despliegue, requiere revisión de Backend y del Project Manager.

## Commits

Use mensajes breves en infinitivo:

- `feat(events): agregar estado de publicación`
- `fix(contacts): validar consentimiento de privacidad`
- `test(news): cubrir transicion de borrador`
- `docs(deploy): documentar respaldo previo`

No mezcle cambios funcionales, formateo masivo y refactorizacion sin relacion en el mismo pull request.

