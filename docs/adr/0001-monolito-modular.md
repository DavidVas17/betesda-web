# ADR-0001: monolito modular con Django y PostgreSQL

- Estado: aceptado
- Fecha: 2026-09-02
- Responsables: equipo del proyecto

## Contexto

El sitio debe ofrecer contenido público, administración autenticada, eventos, noticias, galería, contacto, accesibilidad, seguridad, respaldos y despliegue de bajo costo. El equipo tiene cuatro integrantes y una fecha academica cercana.

## Decision

Se utilizará Django 5.2 LTS con PostgreSQL dentro de una arquitectura monolítica modular. Docker Compose será el contrato del entorno. Caddy terminará HTTPS en despliegues propios. El panel de Django cubrirá la primera versión administrativa y el sitio público usará renderizado del servidor.

## Motivos

- Reduce el número de componentes que el equipo debe integrar y operar.
- Proporciona autenticación, permisos, validación, migraciones y panel administrativo maduros.
- El renderizado del servidor favorece SEO, accesibilidad y carga inicial.
- PostgreSQL permite consultas, indices, respaldo y crecimiento sin cambiar de motor.
- Los módulos mantienen limites claros y pueden extraerse en el futuro si hay evidencia para hacerlo.

## Consecuencias

- Frontend y backend comparten repositorio y ciclo de entrega.
- El equipo debe respetar los limites modulares para evitar acoplamiento.
- No se crea una API REST ni una aplicación SPA durante el MVP.
- Multimedia se almacena en volumen local al inicio; producción sostenible debe migrarla a almacenamiento de objetos antes de escalar horizontalmente.

## Alternativas descartadas

- Microservicios: elevan despliegue, seguridad, trazabilidad y pruebas sin una carga que lo justifique.
- React y API independientes: duplican autenticación, validación y manejo de errores para el plazo disponible.
- CMS generico: reduce control academico sobre la implementación y dificulta demostrar los requerimientos tecnicos del proyecto.

