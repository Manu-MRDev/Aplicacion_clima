# Aplicación Clima

Aplicación climática completa con backend FastAPI y frontend React + TypeScript. Permite autenticación con contraseña y TOTP, consulta del clima actual mediante Open-Meteo, geocodificación inversa con Nominatim, registro de observaciones en PostgreSQL y SQL Server, y verificación de integridad mediante cadenas de hashes.

## Arquitectura

El proyecto está dividido en dos componentes:

```text
Aplicacion_clima/
├── api/   # Backend FastAPI (Python)
└── web/   # Frontend React + TypeScript (Vite)
```

- **Backend**: API REST en `http://localhost:8000`. Los endpoints de negocio usan el prefijo `/api`; los de salud viven en la raíz (`/health/live`, `/health/ready`). Gestiona autenticación, sesiones, registros climáticos, integridad y consultas externas.
- **Frontend**: Aplicación web en `http://localhost:5173`. Se comunica con el backend mediante `fetch` con cookies `HttpOnly` y tokens CSRF.

### Estructura detallada

```text
api/
  app/
    api/            rutas HTTP y dependencias (sesión, CSRF, rate limit)
    core/           configuración, contenedor, seguridad, errores, logging
    models/         modelos de dominio
    repositories/   PostgreSQL y SQL Server (introspección y SQL parametrizado)
    schemas/        contratos Pydantic
    services/       auth, TOTP, sesiones, clima, geocodificación, integridad
  docs/             arquitectura, API, seguridad, TLS, datos, privacidad, pruebas
  scripts/          inspección de esquemas y reset administrativo de TOTP
  tests/            unitarias, API e integración opt-in
  migrations/       vacío a propósito: la API no ejecuta DDL
web/
  src/
    components/     UI, autenticación, clima y registros
    contexts/       sesión, CSRF y estado de autenticación
    hooks/          clima, registros, geolocalización y voz
    pages/          panel, login, alta, historial, nuevo registro e integridad
    routes/         rutas protegidas y navegación
    services/       cliente HTTP y servicios por dominio
    styles/         sistema visual responsive
    tests/          Vitest, Testing Library y fetch simulado
    types/          contrato TypeScript de la API
    utils/          validación, fechas, errores y comandos de voz
```

## Tecnologías

### Backend (`api/`)

- [FastAPI](https://fastapi.dev/) con Uvicorn
- Python >= 3.14
- PostgreSQL 18 y SQL Server 2025 (vía `psycopg` y `pyodbc`)
- Autenticación: Argon2id/bcrypt, TOTP (pyotp), sesiones opacas con rotación
- Criptografía: `cryptography` (AES-256-GCM)
- Integración: Open-Meteo, Nominatim
- Pruebas: pytest

### Frontend (`web/`)

- [React](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
- [Vite](https://vitejs.dev/)
- [Vitest](https://vitest.dev/) + [Testing Library](https://testing-library.com/)
- Web Speech API (comandos de voz)
- Consumo REST con manejo de cookies y CSRF

## Requisitos

### Backend

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 18 accesible
- SQL Server 2025 Express accesible
- unixODBC + `ODBC Driver 18 for SQL Server`
- Opcional: certificados TLS

### Frontend

- Node.js `^20.19.0` o `>=22.12.0` (requisito de Vite 8)
- npm
- Backend Clima API en ejecución

## Base de datos

La API **no crea, altera ni renombra tablas** y no ejecuta migraciones: `api/migrations/` está vacío a propósito. Solo lee metadatos y ejecuta DML parametrizado sobre tablas existentes.

Tablas esperadas:

- **PostgreSQL** (`UPP`): `usuarios`, `session`, `Georreferencia`, `cadena_bloques`.
- **SQL Server** (`UPP`): `dbo.Georreferencia`, `dbo.CadenaBloques`.

La API necesita permisos `SELECT`, `INSERT`, `UPDATE` y `DELETE` sobre esas tablas; no necesita permisos DDL. Las tablas y columnas se inspeccionan en tiempo de ejecución y los identificadores se citan y parametrizan.

Valores por defecto de `.env.example`:

```env
POSTGRES_HOST=192.168.56.10
POSTGRES_PORT=5432
POSTGRES_DB=UPP
SQLSERVER_HOST=192.168.56.11
SQLSERVER_PORT=49834
SQLSERVER_DB=UPP
```

## Configuración e instalación

### 1. Configurar el backend

```bash
cd api
cp .env.example .env

# Generar claves (ejecutar 3 veces, una por clave)
openssl rand -base64 32
openssl rand -base64 32
openssl rand -base64 32
```

Editar `.env` con:

- Credenciales reales de PostgreSQL y SQL Server.
- `SESSION_SECRET_KEY`, `TOTP_ENCRYPTION_KEY`, `RECORD_ENCRYPTION_KEY`: tres claves base64 de 32 bytes **distintas**.
- `GEOCODING_USER_AGENT`: identificador real y correo de contacto (Nominatim puede bloquear identificadores genéricos).
- `CORS_ORIGINS`: orígenes exactos del frontend, nunca `*`.
- `ALLOWED_HOSTS`: hosts aceptados por `TrustedHostMiddleware`.
- `REGISTRATION_ENABLED`: si se permite el alta pública. Sin valor, está activo en desarrollo y desactivado en producción.
- `ODBC_CONFIG_DIR` si se usa el driver local.
- TLS: `SSL_CERTFILE` y `SSL_KEYFILE`.
- `APP_ENV=production` endurece cookies, oculta `/docs`, exige TLS en PostgreSQL y prohíbe `TrustServerCertificate=yes` y `DEBUG=true`.

Ver [api/README.md](api/README.md) para detalles del driver ODBC en Arch/CachyOS.

Instalar dependencias:

```bash
uv sync --dev
```

### 2. Configurar el frontend

```bash
cd web
cp .env.example .env
npm install
```

El `.env.example` solo requiere:

```env
VITE_API_BASE_URL=http://localhost:8000
```

No deben colocarse contraseñas, secretos TOTP, cookies, tokens CSRF ni claves del backend en variables `VITE_*`: cualquier valor `VITE_*` termina incluido en el bundle.

## Ejecución

### Desarrollo

Terminal 1 - Backend:

```bash
cd api
uv run python -m app
# API y documentación en http://127.0.0.1:8000/docs
```

Terminal 2 - Frontend:

```bash
cd web
npm run dev
# Frontend en http://localhost:5173
```

**Importante**: abrir el frontend con `localhost` (no `127.0.0.1`), ya que el backend solo admite `http://localhost:5173` en `CORS_ORIGINS` por defecto. Si necesitas usar `127.0.0.1`, añade ese origen exacto a `CORS_ORIGINS`.

`/docs`, `/redoc` y `/openapi.json` solo están disponibles en desarrollo. En producción se desactivan siempre.

### Producción

#### Backend con TLS directo

```bash
APP_ENV=production SESSION_SECURE_COOKIES=true DOCS_ENABLED=false \
REGISTRATION_ENABLED=false POSTGRES_SSLMODE=require \
ALLOWED_HOSTS='["clima.example.org"]' \
CORS_ORIGINS='["https://clima.example.org"]' \
SSL_CERTFILE=/ruta/cert.pem SSL_KEYFILE=/ruta/key.pem \
uv run python -m app
```

Si TLS termina en un proxy inverso, ejecuta Uvicorn en `127.0.0.1` y configura `TRUSTED_PROXIES` con la IP del proxy. Ver [api/docs/tls.md](api/docs/tls.md).

#### Frontend con proxy inverso (recomendado)

```bash
cd web
VITE_API_BASE_URL= npm run build
```

Sirve `dist/` con nginx/Caddy y reenvía `/api/` y `/health/` al backend bajo el mismo origen. Así la cookie `__Host-clima_session` y `SameSite=Lax` funcionan sin CORS. Ver [web/README.md](web/README.md) para la configuración completa de nginx.

`vite preview` no es un servidor de producción y su puerto no está incluido en el CORS de desarrollo.

## Funcionalidades principales

### Autenticación y seguridad

- Registro opcional controlado por `REGISTRATION_ENABLED`.
- Login con usuario y contraseña; segundo factor TOTP obligatorio antes de obtener acceso.
- Inscripción TOTP con QR y clave manual, mostrada una sola vez.
- Sesiones opacas con rotación al autenticar, expiración inactiva y absoluta.
- Cookies `HttpOnly`, `Secure` en producción, `SameSite=Lax` y `Path=/`.
- Protección CSRF con token HMAC ligado al `sid`; cabecera `X-CSRF-Token` en escrituras.
- Comprobación de `Origin` y `Sec-Fetch-Site`.
- Bloqueo temporal por intentos fallidos y rate limiting por IP/cuenta.
- Contraseñas con Argon2id; los hashes bcrypt heredados se rehashean tras un login correcto.
- Cabeceras de seguridad, redacción de logs sensibles y cuerpo máximo de 1 MiB comprobado con `Content-Length`.
- Rate limiting en memoria **por proceso**; el bloqueo de cuentas sí es global porque se guarda en PostgreSQL.

### Flujo de autenticación

1. `POST /api/auth/register` (opcional) con `username` y `password` crea la cuenta y deja una sesión pendiente de inscripción TOTP.
2. `POST /api/auth/login` con `username` y `password`.
3. Si el usuario no tiene TOTP: `enrollment_required`; llamar a `/api/auth/totp/enroll` y confirmar con `/api/auth/totp/confirm`.
4. Si ya tiene TOTP: `totp_required`; llamar a `/api/auth/totp/verify`.
5. La sesión se rota al autenticar. `GET /api/auth/me` devuelve usuario, CSRF y expiración.
6. `POST /api/auth/logout` revoca la sesión y borra la cookie.

Política de alta:

- `username`: 3-64 caracteres; debe empezar por letra o número y admite letras, números, punto, guion y guion bajo.
- `password`: 12-128 caracteres y al menos tres tipos entre minúsculas, mayúsculas, números y símbolos.

### Meteorología y registros

- Consulta del clima actual (Open-Meteo) sin consulta automática al entrar.
- Geolocalización solo al pulsar el botón correspondiente; si se rechaza el permiso, se pueden introducir coordenadas manuales.
- Geocodificación inversa (Nominatim); si falla, el clima y las coordenadas siguen visibles y se muestra un resultado parcial.
- Creación de registros en PostgreSQL (`ubuntu`) o SQL Server (`windows`).
- `paterno` es obligatorio cuando el destino es SQL Server (`windows`).
- El `usuario` y el `id` no se aceptan en el cuerpo: se derivan de la sesión y de la base de datos.
- Historial con filtros por servidor, usuario, rango de fechas, límite y ordenamiento.
- La paginación combinada (`servidor=ambos`) se aplica por fuente, no como total global.
- Detalle de registro por `id` **y** `servidor`, porque los IDs se repiten entre bases.
- Si una fuente falla, la respuesta se marca como parcial y muestra los registros de la fuente disponible.

### Integridad de cadenas

- El registro y su bloque se crean en la misma transacción cuando la integridad está disponible.
- Cadenas independientes por servidor: `api-ubuntu` y `api-windows`.
- Génesis de 64 ceros; hash SHA-256 en 64 hex, sin prefijo.
- Payload versionado: `canon-v1` para el registro y `block-v1` para el bloque.
- PostgreSQL serializa la cadena con `pg_advisory_xact_lock`; SQL Server usa `UPDLOCK, HOLDLOCK`.
- Estados de integridad al crear: `created`, `disabled` (`INTEGRITY_ENABLED=false`) y `unavailable` (tabla ausente/incompatible o bloque no confirmado). Un registro guardado sin bloque **no** se presenta como protegido.
- La verificación comprueba bloques, hashes y que cada registro referenciado siga coincidiendo.
- Los registros sin bloque se informan como advertencia, no como fallo.
- Las cadenas heredadas `ubuntu`/`windows` no se verifican con el formato `canon-v1`/`block-v1`.

### Comandos de voz (frontend)

- Reconocimiento de voz para guardar registros: "Guardar en servidor 1/2", "Guardar en Ubuntu/Windows".
- "Servidor 1" corresponde a PostgreSQL/Ubuntu y "servidor 2" a SQL Server/Windows.
- No guarda automáticamente: rellena el destino y abre el diálogo de confirmación.
- El micrófono se detiene al obtener un resultado, al producirse un error, a los 12 segundos o al desmontar el componente.
- Depende de `SpeechRecognition`/`webkitSpeechRecognition` (principalmente Chromium y contextos seguros: HTTPS o `localhost`).

## Endpoints principales

Prefijo de negocio: `/api`. Los endpoints de salud viven en la raíz.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `/api/auth/register` | Público + `Origin` | Crea una cuenta y deja una sesión pendiente de TOTP |
| POST | `/api/auth/login` | Público + `Origin` | Contraseña; crea sesión pendiente de TOTP |
| POST | `/api/auth/totp/verify` | Sesión pendiente + CSRF | Verifica TOTP y rota la sesión |
| POST | `/api/auth/totp/enroll` | Sesión pendiente + CSRF | Genera secreto, URI y QR (una vez) |
| POST | `/api/auth/totp/confirm` | Sesión pendiente + CSRF | Confirma la inscripción y autentica |
| POST | `/api/auth/logout` | Sesión + CSRF | Revoca la sesión |
| GET | `/api/auth/me` | Sesión autenticada | Usuario y CSRF actuales |
| GET | `/api/weather/current?lat=&lon=` | Público | Clima actual (Open-Meteo) |
| GET | `/api/locations/reverse?lat=&lon=` | Público | Geocodificación inversa (Nominatim) |
| POST | `/api/records` | Sesión + CSRF | Crea un registro en un servidor |
| GET | `/api/records` | Sesión autenticada | Lista registros de `ubuntu`, `windows` o `ambos` |
| GET | `/api/records/{id}?servidor=` | Sesión autenticada | Obtiene un registro |
| GET | `/api/integrity/verify?servidor=` | Sesión autenticada | Verifica la cadena de hashes |
| GET | `/health/live` | Público | Proceso vivo (sin prefijo `/api`) |
| GET | `/health/ready?strict=` | Público | Dependencias (sin prefijo `/api`) |

Detalles de contrato:

- `GET /api/records` acepta `servidor` (`ubuntu` por defecto, `windows` o `ambos`), `usuario`, `desde`, `hasta`, `limit` (1-200, por defecto 50), `offset`, `orden` (`fecha_hora` o `id`) y `direccion` (`asc`/`desc`). Todos los usuarios autenticados ven todos los registros; `usuario` es un filtro opcional.
- `GET /api/integrity/verify` usa `servidor=ambos` por defecto.
- Las escrituras requieren el token CSRF devuelto por el login o por `GET /api/auth/me`, en la cabecera `X-CSRF-Token`.
- `/health/ready` devuelve `status: ok`, `degraded` o `error`; con `strict=true` responde 503 si el estado no es `ok`. El resultado se cachea durante 3 segundos para no saturar los sondeos.
- El límite de cuerpo es de 1 MiB y se comprueba con `Content-Length`; un proxy debe imponer además un límite real.

Ver [api/docs/api.md](api/docs/api.md) para el contrato completo.

## Pruebas

### Backend

```bash
cd api
uv run pytest -q                         # Unitarias + API, sin bases reales
RUN_DB_INTEGRATION=1 uv run pytest -q    # Incluye PostgreSQL y SQL Server
```

Las pruebas de integración escriben dentro de una transacción y terminan siempre en `ROLLBACK`; no dejan filas. Ver [api/docs/pruebas.md](api/docs/pruebas.md).

### Frontend

```bash
cd web
npm run typecheck
npm test
npm run build
```

`npm run test:coverage` genera cobertura con V8 y `npm run test:watch` ejecuta Vitest en modo interactivo. `npm run build` incluye el typecheck.

### Resultados verificados

Comprobados en este host el 2026-10-26:

| Suite | Resultado |
|---|---|
| `api`: `uv run pytest -q` | 235 aprobadas, 7 omitidas (integración) |
| `api`: `RUN_DB_INTEGRATION=1 uv run pytest -q` | 242 aprobadas (según `api/docs/pruebas.md`) |
| `web`: `npm test` | 10 archivos, 88 pruebas aprobadas |

## Documentación detallada

### Backend

- [Arquitectura](api/docs/arquitectura.md)
- [API](api/docs/api.md)
- [Seguridad](api/docs/seguridad.md)
- [TLS](api/docs/tls.md)
- [Mapeo de bases de datos](api/docs/base-de-datos.md)
- [Privacidad](api/docs/privacidad.md)
- [Pruebas](api/docs/pruebas.md)
- [Pendientes y acciones manuales](api/docs/pendientes.md)

### Frontend

- [README del frontend](web/README.md)

## Solución de problemas

- **403 al iniciar sesión o guardar**: el `Origin` no coincide con `CORS_ORIGINS`, o se abrió `127.0.0.1` en vez de `localhost`.
- **401 tras recargar**: la cookie no llegó al backend por un origen/puerto distinto o por una política de cookies del navegador.
- **La sesión se cierra**: el backend devolvió `401`; el frontend limpia el estado y avisa de sesión terminada.
- **El micrófono no aparece**: el navegador no implementa Web Speech API, no es un contexto seguro o se denegó el permiso. Usa el formulario manual.
- **El clima falla pero la página responde**: revisa `/health/ready` y los límites de Open-Meteo/Nominatim; el frontend no sustituye datos externos.
- **`/docs` no aparece**: es intencional en producción; solo se publica en desarrollo.
- **Error de driver ODBC**: revisa `ODBC_CONFIG_DIR` o instala el driver globalmente. Ver [api/README.md](api/README.md).

## Limitaciones conocidas

- **TOTP heredado**: los secretos cifrados con el formato anterior (sin prefijo `v1.`) no se pueden descifrar. Requieren reset administrativo con `scripts/admin_reset_totp.py` (primero sin `--apply`).
- **Rate limiting**: en memoria por proceso; con varios workers no es global. Para un límite global usa Redis o un proxy con límites.
- **Sin anclaje externo**: borrar el último bloque y su registro no es detectable solo con la base de datos.
- **IDs no únicos globalmente**: los IDs se repiten entre PostgreSQL y SQL Server; cualquier consulta debe enviar siempre `servidor`.
- **Paginación combinada**: es por fuente y no ofrece un total global.
- **Cadenas heredadas**: `ubuntu` y `windows` no se verifican con `canon-v1`/`block-v1`.
- **Registros sin bloque**: la tabla es compartida con la aplicación heredada; los registros históricos o de otros procesos se informan como advertencia.
- **Sin búsqueda de ciudades**: no hay endpoint de búsqueda directa; la ubicación se obtiene por geolocalización o coordenadas y se resuelve con geocodificación inversa.
- **Sin gestión de cuentas**: no hay verificación de correo, recuperación de contraseña, roles, panel de administración ni borrado de cuentas desde la interfaz.
- **Sesiones expiradas**: `SessionService.delete_expired()` no tiene tarea programada; conviene programar una limpieza.
- **Comandos de voz**: dependen de Web Speech API (principalmente Chromium y contexto seguro) y el audio puede enviarse a servidores del proveedor.
- **Alta pública**: desactivada por defecto en producción; puede habilitarse explícitamente con `REGISTRATION_ENABLED=true`.
- **Límite de cuerpo**: se comprueba con `Content-Length`; un proxy debe imponer además un límite real.

## Notas importantes

- Nunca commitear `.env`, certificados, claves privadas, cookies o tokens.
- La API no crea tablas ni ejecuta migraciones; las tablas deben existir antes de arrancar.
- En producción, `APP_ENV=production` endurece cookies, oculta `/docs`, exige TLS en PostgreSQL y prohíbe `DEBUG=true` y `TrustServerCertificate=yes`.
- Las cookies son `HttpOnly` y se rotan al autenticar; en producción el nombre es `__Host-clima_session` y en desarrollo `clima_session`.
- El frontend nunca almacena credenciales, códigos TOTP, CSRF ni cookies en `localStorage`/`sessionStorage`.
- Todas las peticiones del frontend pasan por `web/src/services/apiClient.ts`, con `credentials: "include"`, `cache: "no-store"` y timeout de 15 segundos.
- Los mensajes de error muestran el mensaje seguro del backend o un texto genérico; nunca trazas, SQL ni rutas internas.
