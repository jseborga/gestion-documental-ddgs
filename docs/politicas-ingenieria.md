# Políticas de ingeniería e implementación

Versión 0.1 · 16/11/2026 · Obligatorias para todo el que modifique el código (proveedor, Gobernación o terceros). Objetivo: que el sistema siga siendo escalable y mantenible aunque cambie el equipo.

## 1. Principios
1. **Lo simple primero.** Monolito modular; se agrega una pieza (servicio, cola, caché) solo con un ADR que muestre el problema medido que resuelve.
2. **El código se explica solo; las decisiones, en ADR.** Toda decisión de arquitectura queda en `docs/adr/NNNN-titulo.md` (contexto, decisión, alternativas, consecuencias).
3. **Lo que no está probado no existe.** Ningún cambio sin prueba automática que lo cubra.
4. **Configuración fuera del código.** Nada institucional ni secreto en el repositorio (SPEC.md §16).
5. **Todo cambio es reversible.** Despliegues, migraciones y configuraciones tienen camino de vuelta documentado.

## 2. Stack fijo (cambiarlo requiere ADR)
| Capa | Elección | Política de versiones |
| --- | --- | --- |
| Lenguaje | Python 3.12 | Subir de versión menor una vez al año, dentro del soporte de Django |
| Framework | Django 5.2 LTS | Migrar a la siguiente LTS antes de que termine el soporte de la actual (5.2 → abril 2028) |
| Base de datos | PostgreSQL 17 + pgvector 0.8.x | Actualizar menor cada trimestre; mayor cada 2 años |
| Vectores | pgvector en la misma base | No agregar otra base vectorial salvo ADR con medición |
| Almacenamiento | API S3 (SeaweedFS por defecto) | El código solo usa la API S3 |
| Interfaz | Plantillas Django + HTMX | Sin frameworks SPA salvo ADR |
| Gestor de dependencias | `uv` con archivo de bloqueo | Bloqueo versionado en el repositorio |

## 3. Estructura y módulos
- Una app Django por dominio (`core`, `correspondencia`, `archivos`, `seguridad`, `auditoria`, `eventos`, `importacion`, `api`, `tablero`; luego `obras`, `poa`, `activos`, `interop`, `ia`).
- Cada app expone `services.py` (escritura) y `selectors.py` (consultas). Otras apps solo usan esas funciones.
- Prohibido importar modelos de otra app para escribir en ellos. Se verifica con `import-linter` en CI.
- Tamaño orientativo: si una app supera ~5.000 líneas o tiene un equipo propio, evaluar separarla (ADR).

## 4. Flujo de trabajo con Git
- Rama principal `main`, siempre desplegable. Ramas cortas `tipo/descripcion` (máx. ~3 días).
- Mensajes con *Conventional Commits* (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `security:`).
- Todo cambio entra por *pull request* con al menos una revisión aprobada y CI en verde. Nadie integra su propio PR sin revisión (excepto parches de seguridad urgentes, revisados después en 24 h).
- Plantilla de PR: qué cambia, por qué, cómo se probó, impacto en datos/migraciones, documentación actualizada (sí/no).

## 5. Integración continua (bloqueante)
1. `ruff check` y `ruff format --check`
2. `import-linter` (límites entre módulos)
3. `pytest` con PostgreSQL real (no SQLite) y cobertura ≥ 80 % en `services.py` y `apps/seguridad`
4. Controles de seguridad de `docs/seguridad.md` §3
5. `manage.py makemigrations --check` (no quedan migraciones sin crear)
6. Construcción de la imagen Docker

## 6. Base de datos y migraciones
- Migraciones pequeñas, una intención por migración, siempre con prueba de ida y vuelta en CI.
- Cambios que rompen compatibilidad se hacen en dos versiones (*expand → contract*): agregar columna nueva, copiar datos, cambiar código, retirar columna en la versión siguiente.
- Prohibido editar una migración ya publicada.
- Índices pensados desde el inicio para las búsquedas de SPEC.md §8 (CITE, HR, asunto full-text, fechas, estado).
- Vectores (fase IA): tabla separada `fragmento_documento(documento_id, orden, texto, embedding vector(n))` con índice HNSW, para no inflar las tablas de negocio; los filtros de permisos se aplican en la misma consulta.

## 7. Versionado y entregas
- Versionado semántico `MAYOR.MENOR.PARCHE`; etiqueta Git por versión; `CHANGELOG.md` actualizado en el mismo PR.
- Cada entrega a la institución: notas de versión, lista de migraciones, pasos de actualización y de reversión, resultado de CI. Sirve como acta de aceptación del contrato.

## 8. Entornos y despliegue
| Entorno | Para qué | Datos |
| --- | --- | --- |
| `dev` | Desarrollo local con Docker Compose | Sintéticos |
| `staging` | Prueba de la versión antes de producción, misma configuración que producción | Copia anonimizada o sintéticos |
| `prod` | Uso real | Reales |

- Despliegue con etiqueta de imagen fija (nunca `latest`).
- Antes de actualizar producción: respaldo verificado; después: prueba de humo automática (`/api/v1/salud/` + flujo básico).
- Reversión: volver a la imagen anterior + restaurar base solo si la migración no es reversible (por eso se exige *expand → contract*).

## 9. Escalabilidad (en orden; no saltar pasos sin medición)
1. Índices y consultas optimizadas (revisar con `EXPLAIN`).
2. Más *workers* de gunicorn y del proceso de eventos.
3. Servidor más grande (vertical).
4. Réplica de lectura de PostgreSQL para tablero y búsqueda.
5. Caché (Redis) para tablero y catálogos.
6. Separar un módulo como servicio (ADR obligatorio).

Metas de rendimiento iniciales: 95 % de páginas < 500 ms y API < 300 ms con 50 usuarios concurrentes; medidas con una prueba de carga (`locust`) en `staging` antes de cada versión mayor.

## 10. Documentación como código
- Todo en Markdown dentro de `docs/`, publicado con MkDocs; se actualiza en el mismo PR que el cambio.
- Obligatorios: arquitectura (con diagrama), modelo de datos, API (OpenAPI generada), manual por rol, instalación, actualización, respaldo/restauración, incidentes, ADR, CHANGELOG.
- Una funcionalidad no está terminada si su documentación no está actualizada.

## 11. Definición de terminado (cada historia o tarea)
- [ ] Código revisado y CI en verde
- [ ] Pruebas nuevas que fallaban antes del cambio
- [ ] Permisos verificados con `puede(...)` y prueba
- [ ] Bitácora y eventos emitidos si cambia un estado
- [ ] Migración reversible (si aplica)
- [ ] Documentación y CHANGELOG actualizados
- [ ] Sin datos reales ni secretos en el repositorio

## 12. Mantenimiento programado
| Frecuencia | Tarea |
| --- | --- |
| Mensual | Actualización de dependencias, revisión de alertas de seguridad, prueba de restauración automática |
| Trimestral | Restauración completa en entorno limpio, revisión de accesos y cuentas, versiones menores de PostgreSQL |
| Anual | Revisión de la matriz ASVS, prueba de penetración, plan de migración de versiones LTS |
