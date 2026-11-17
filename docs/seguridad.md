# Módulo de seguridad

Versión 0.1 · 16/11/2026 · Forma parte de `SPEC.md` (§13). Si hay conflicto, este documento manda en temas de seguridad.

## 1. Marco de referencia

| Referencia | Cómo se usa |
| --- | --- |
| **OWASP ASVS 5.0 (mayo 2025), nivel 2** | Lista de verificación de requisitos de seguridad de la aplicación. Nivel 2 porque el sistema maneja información institucional y datos personales. Se guarda una matriz de cumplimiento en `docs/asvs-matriz.md`. |
| **PISI de la Gobernación** | El DS 5519 dispone que las entidades del sector público implementen su Plan Institucional de Seguridad de la Información según lineamientos del CGII. El sistema debe ajustarse al PISI de la Gobernación (roles, clasificación, incidentes). Pedir el documento vigente al Responsable de Seguridad de la Información. |
| **Lineamientos AGETIC / CGII** | Gestión y reporte de incidentes; evaluaciones de seguridad a sistemas de entidades públicas. |
| **Sin ley general de datos personales (a nov-2026)** | Se aplican igualmente principios de minimización, finalidad y control de acceso; diseñar para cumplir una futura ley sin rehacer el sistema. |

## 2. App `apps/seguridad`

Centraliza autenticación, autorización, clasificación, sesiones y registros de seguridad. Las demás apps la consumen; no implementan controles propios.

### 2.1 Autenticación
- Usuario y contraseña con validadores de Django (mínimo 12 caracteres, lista de contraseñas comunes, no similar al usuario).
- **Segundo factor (TOTP)** obligatorio para `administrador`, `director` y `auditor`; opcional para el resto (configurable a obligatorio). Códigos de recuperación de un solo uso.
- Bloqueo progresivo tras intentos fallidos (`django-axes`): 5 intentos → 15 min; registro en bitácora de seguridad.
- Preparado para OIDC (Keycloak / Ciudadanía Digital) sin cambiar el modelo de permisos: el proveedor solo autentica; los cargos y permisos siguen en el sistema.
- Alta y baja de usuarios ligadas a `OcupacionCargo`: al terminar la última ocupación vigente, la cuenta se desactiva automáticamente (tarea diaria del worker) y se notifica al administrador.

### 2.2 Sesiones
- Cookie `Secure`, `HttpOnly`, `SameSite=Lax`; cierre por inactividad a los 30 min (configurable) y máximo absoluto de 10 h.
- Rotación del identificador de sesión al iniciar sesión y al elevar privilegios.
- Pantalla "mis sesiones" para cerrar sesiones abiertas en otros equipos.

### 2.3 Autorización
- **RBAC**: grupos de SPEC.md §7.
- **ABAC** (atributos) evaluado en un único servicio `puede(usuario, accion, objeto)`: unidad del objeto, cargos vigentes del usuario (incluidas suplencias), clasificación del expediente, estado del documento.
- Prohibido decidir permisos en plantillas o vistas: siempre `puede(...)`. Pruebas unitarias por cada combinación rol × acción × clasificación.
- Mínimo privilegio: nadie tiene permisos por defecto; el superusuario de Django solo para emergencias, con 2FA y alerta en cada uso.

### 2.4 Clasificación de la información
| Nivel | Ejemplos | Quién ve |
| --- | --- | --- |
| `publico` | Comunicados | Cualquier usuario autenticado de la entidad |
| `interno` (por defecto) | Notas, informes técnicos | Usuarios de la unidad |
| `confidencial` | Personal, procesos legales, contencioso | Cargos derivados, director(a), auditor |
| `reservado` | Lo que el PISI defina | Lista explícita de cargos |

Cada acceso a un expediente `confidencial` o `reservado` (ver, descargar) queda en bitácora. Los niveles y sus reglas se ajustan al PISI.

### 2.5 Protección de datos
- **En tránsito**: TLS 1.2+ (preferible 1.3) en el proxy inverso; HSTS; redirección forzada a HTTPS.
- **En reposo**: cifrado de disco en el servidor (LUKS o equivalente); los respaldos se cifran siempre en origen (restic, ver `docs/respaldos.md`).
- **Archivos**: nunca públicos; descarga por vista que verifica permisos o URL firmada de 5 minutos; tipo validado por contenido real (magic bytes), no por extensión; tamaño máximo; antivirus opcional (contenedor ClamAV, perfil `antivirus`) antes de aceptar el adjunto.
- **Minimización**: no guardar CI ni datos personales que el proceso no requiera; los datos de prueba siempre sintéticos.
- **Integridad**: SHA-256 de cada adjunto; verificación periódica (tarea mensual) que compara el hash guardado con el archivo almacenado y alerta discrepancias.

### 2.6 API
- Tokens por integración (no por persona), con permisos limitados (`scopes`), fecha de expiración y registro de uso.
- Limitación de frecuencia (DRF throttling): por usuario y por token.
- CORS cerrado por defecto; lista blanca explícita.
- Errores sin detalles internos; trazas solo en registros.

### 2.7 Cabeceras y navegador
CSP estricta (sin `unsafe-inline`; HTMX y estáticos servidos localmente), `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, protección CSRF de Django en todos los formularios y peticiones HTMX.

### 2.8 Registros y monitoreo
- Registros en JSON a la salida estándar del contenedor (sin datos sensibles ni contraseñas).
- **Bitácora de seguridad** (append-only, igual que la de negocio): inicios y fallos de sesión, bloqueos, cambios de permisos u ocupaciones, uso de tokens, descargas de confidenciales, uso del superusuario.
- Alertas por correo al administrador: 10+ fallos de sesión en 10 min, uso del superusuario, fallo de respaldo, discrepancia de hash.

### 2.9 Gestión de incidentes
Procedimiento en `docs/incidentes.md` (lo redacta el proveedor y lo aprueba la Gobernación): detección, contención, comunicación al Responsable de Seguridad de la Información, reporte al CGII según el PISI, restauración desde respaldo y lecciones aprendidas. El contrato de mantenimiento fija tiempos de respuesta por severidad.

## 3. Seguridad en el desarrollo (CI obligatorio)

| Control | Herramienta | Bloquea la integración si… |
| --- | --- | --- |
| Análisis estático de seguridad | `ruff` (reglas `S`) + `bandit` | hay hallazgos de severidad media o alta sin justificar |
| Vulnerabilidades en dependencias | `pip-audit` + Dependabot | hay vulnerabilidad conocida con parche disponible |
| Secretos en el código | `gitleaks` | aparece cualquier secreto |
| Imagen de contenedor | `trivy` | hay vulnerabilidades críticas con parche |
| Revisión de Django | `manage.py check --deploy` | hay advertencias en configuración de producción |
| Pruebas de autorización | `pytest` | falla cualquier prueba de `puede(...)` |

Además: dependencias con versión fijada (`uv.lock` o `requirements.txt` con hashes); actualización mensual programada; imagen base mínima y usuario no root; prueba de penetración externa antes de producción y una vez al año (puede solicitarse la evaluación de seguridad que ofrece AGETIC/CGII a entidades públicas).

## 4. Criterios de aceptación de seguridad
1. Matriz ASVS 5.0 nivel 2 completada, con justificación de cada requisito no aplicable.
2. `check --deploy`, `bandit`, `pip-audit`, `gitleaks` y `trivy` sin hallazgos bloqueantes.
3. Pruebas de autorización cubren todos los roles × acciones × clasificaciones.
4. 2FA operativo para roles privilegiados; bloqueo por intentos verificado.
5. Restauración de respaldo cifrado probada (ver `docs/respaldos.md`).
