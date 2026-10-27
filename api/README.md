# Clima API

Backend de la aplicación climática. Expone autenticación con contraseña y TOTP,
consultas a Open-Meteo, geocodificación inversa con Nominatim, registros
climáticos en PostgreSQL y SQL Server, y verificación de integridad mediante
cadenas de hashes.

> Solo backend. No incluye frontend, migraciones ni DDL automático.

## Estado verificado

Resultados obtenidos en este host (CachyOS, Python 3.14.8):

| Comprobación | Resultado |
|---|---|
| `uv run pytest -q` | 235 pruebas unitarias/API aprobadas; 7 de integración omitidas |
| `RUN_DB_INTEGRATION=1 uv run pytest -q tests/integration` | 7/7 aprobadas |
| `RUN_DB_INTEGRATION=1 uv run pytest -q` | 242/242 aprobadas |
| Readiness real | `status: ok`; PostgreSQL y SQL Server `up`; esquemas y sesiones `ok` |
| Inserción PostgreSQL con rollback | fila y bloque dentro de la transacción; 0 filas persistidas |
| Inserción SQL Server con rollback | fila y bloque dentro de la transacción; 0 filas persistidas |
| Verificación de integridad | cadenas `api-ubuntu`/`api-windows` vacías (`empty`); 12 y 6 registros heredados sin bloque, informados como advertencia |
| Flujo HTTP de autenticación | alta real + TOTP + `/me` + logout validados contra PostgreSQL con cuenta temporal eliminada; login de cuenta preexistente pendiente |

Las secuencias avanzaron por las pruebas con rollback: PostgreSQL quedó en
`last_value=22` y SQL Server en `IDENT_CURRENT=1013`. No quedaron filas de
prueba.

## Requisitos

- Python 3.14 o superior (el proyecto fija `requires-python = ">=3.14"`).
- [uv](https://docs.astral.sh/uv/).
- PostgreSQL 18 accesible en `192.168.56.10:5432`.
- SQL Server 2025 Express accesible en `192.168.56.11:49834`.
- unixODBC y el driver `ODBC Driver 18 for SQL Server`.
- Opcional: certificados TLS para producción.

### CachyOS / Arch

```bash
sudo pacman -Syu --needed unixodbc openssl base-devel
# Opcional, solo si quieres usar psql para el script SQL de reset:
# sudo pacman -S postgresql
curl -LsSf https://astral.sh/uv/install.sh | sh
cd /home/manu/Documentos/Aplicacion_clima/api
uv sync --dev
```

El driver de Microsoft no está en los repositorios oficiales de Arch. En este
host se extrajo localmente en:

```text
/home/manu/.local/share/clima-api/odbc/
├── odbcinst.ini
└── msodbcsql18/lib64/libmsodbcsql-18.6.so.2.1
```

Configura `ODBC_CONFIG_DIR` en `.env` con ese directorio. La aplicación exporta
`ODBCSYSINI` antes de resolver el driver, por lo que no hace falta tocar
`/etc/odbcinst.ini`. Si el driver se instala de forma global, deja
`ODBC_CONFIG_DIR=` vacío.

Comprobación rápida:

```bash
uv run python -c "from app.repositories.pool import SqlServerManager; from app.core.config import get_settings; print(SqlServerManager(get_settings()).driver_missing)"
# False
```

## Configuración

```bash
cp .env.example .env
openssl rand -base64 32   # ejecutar tres veces, una por clave
```

En `.env`:

- `POSTGRES_PASSWORD` y `SQLSERVER_PASSWORD` reales.
- `SESSION_SECRET_KEY`, `TOTP_ENCRYPTION_KEY`, `RECORD_ENCRYPTION_KEY`: tres
  claves base64 de 32 bytes **distintas**.
- `GEOCODING_USER_AGENT`: identificador real y correo de contacto. Nominatim
  puede bloquear identificadores genéricos.
- `CORS_ORIGINS`: orígenes exactos del frontend, nunca `*`.
- `ALLOWED_HOSTS`: hosts aceptados por `TrustedHostMiddleware`.
- `REGISTRATION_ENABLED`: si se permite `POST /api/auth/register`. Sin valor,
  está activo en desarrollo y desactivado en producción; puede habilitarse
  explícitamente en producción.
- `ODBC_CONFIG_DIR` si usas el driver local.
- TLS: `SSL_CERTFILE` y `SSL_KEYFILE`.
- `APP_ENV=production` endurece cookies, oculta `/docs`, exige TLS en PostgreSQL
  y prohíbe `TrustServerCertificate=yes` y `DEBUG=true`.

Nunca versiones `.env`, certificados ni claves privadas (ya están en
`.gitignore`).

## Ejecución

Desarrollo:

```bash
uv run python -m app
# http://127.0.0.1:8000/docs
```

Producción con TLS directo:

```bash
APP_ENV=production SESSION_SECURE_COOKIES=true DOCS_ENABLED=false \
REGISTRATION_ENABLED=false POSTGRES_SSLMODE=require \
SSL_CERTFILE=/ruta/cert.pem SSL_KEYFILE=/ruta/key.pem \
uv run python -m app
```

También puedes usar Uvicorn directamente:

```bash
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Con varios workers, el rate limiting en memoria es por proceso. Para un límite
global usa Redis o un proxy con límites; el bloqueo de cuentas sí es global
porque se guarda en PostgreSQL.

### TLS

Para desarrollo local:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -nodes -days 365 \
  -keyout certs/dev-key.pem -out certs/dev-cert.pem \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

Para producción se recomienda terminar TLS en Caddy/nginx y ejecutar Uvicorn en
`127.0.0.1`; configura `TRUSTED_PROXIES` con la IP del proxy. Detalles en
[docs/tls.md](docs/tls.md).

## Endpoints

Prefijo: `/api`.

| Método | Ruta | Autenticación | Descripción |
|---|---|---|---|
| POST | `/auth/register` | No | Crea una cuenta y deja una sesión pendiente de TOTP |
| POST | `/auth/login` | No | Contraseña; crea sesión pendiente de TOTP |
| POST | `/auth/totp/verify` | Sesión pendiente | Verifica TOTP y rota la sesión |
| POST | `/auth/totp/enroll` | Sesión pendiente | Genera secreto, URI y QR (una vez) |
| POST | `/auth/totp/confirm` | Sesión pendiente | Confirma la inscripción y autentica |
| POST | `/auth/logout` | Sesión + CSRF | Revoca la sesión |
| GET | `/auth/me` | Sesión autenticada | Usuario y CSRF actuales |
| GET | `/weather/current?lat=&lon=` | No | Clima actual (Open-Meteo) |
| GET | `/locations/reverse?lat=&lon=` | No | Geocodificación inversa (Nominatim) |
| GET | `/records` | Sesión autenticada | Lista registros de `ubuntu`, `windows` o `ambos` |
| POST | `/records` | Sesión + CSRF | Crea registro en un servidor |
| GET | `/records/{id}?servidor=` | Sesión autenticada | Obtiene un registro |
| GET | `/integrity/verify?servidor=` | Sesión autenticada | Verifica la cadena de hashes |
| GET | `/health/live` | No | Proceso vivo |
| GET | `/health/ready?strict=` | No | Dependencias |

`GET /records` acepta `usuario`, `desde`, `hasta`, `limit` (1-200), `offset`,
`orden` (`fecha_hora` o `id`) y `direccion` (`asc`/`desc`). Todos los usuarios
autenticados ven todos los registros; `usuario` es un filtro opcional.

El identificador de usuario y el `id` del registro **nunca** se aceptan en el
cuerpo de creación: se derivan de la sesión y de la base de datos.

Contrato detallado en [docs/api.md](docs/api.md).

## Autenticación

1. Opcionalmente, `POST /api/auth/register` con `username` y `password` crea la
   cuenta. La contraseña debe tener entre 12 y 128 caracteres y combinar al
   menos tres tipos de caracteres. La respuesta deja una sesión pendiente de
   inscripción TOTP.
2. `POST /api/auth/login` con `username` y `password`.
3. Si el usuario no tiene TOTP: `enrollment_required`. Llamar a
   `POST /api/auth/totp/enroll` y luego `confirm` con un código de 6 dígitos.
4. Si ya tiene TOTP: `totp_required`. Llamar a `POST /api/auth/totp/verify`.
5. La sesión se rota al autenticar. La cookie es opaca, `HttpOnly`, `Secure` en
   producción, `SameSite=Lax` por defecto y `Path=/`.
6. Las operaciones de escritura exigen el token CSRF devuelto por el login o por
   `GET /api/auth/me`, en la cabecera `X-CSRF-Token`.

El registro no acepta `id`, `totp_enabled`, `usuario` ni ningún otro campo. La
cuenta se crea sin segundo factor y no obtiene acceso hasta confirmar TOTP.
`REGISTRATION_ENABLED=false` desactiva el alta; sin la variable, el alta queda
activa en desarrollo y desactivada en producción.

Ejemplo:

```bash
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"ana","password":"..."}'

# Guardar csrf_token de la respuesta y usarlo:
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/auth/totp/verify \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{"code":"123456"}'
```

### TOTP heredado

Los usuarios cuyos secretos fueron cifrados por la aplicación anterior no se
pueden descifrar con el formato `v1.` de esta API. Deben resetearse de forma
administrativa:

Primero un dry-run (no modifica nada):

```bash
uv run python scripts/admin_reset_totp.py --username ana
```

Si el estado mostrado es el esperado:

```bash
uv run python scripts/admin_reset_totp.py --username ana --apply
```

También existe la variante SQL con `psql` (requiere el cliente instalado):

```bash
psql "host=192.168.56.10 dbname=UPP user=tux" \
  -v username='ana' -f scripts/admin_reset_totp.sql
```

Ambos borran el secreto, desactivan TOTP, limpian bloqueos y revocan las
sesiones de esta API. En el siguiente login el usuario inscribirá TOTP de nuevo.
No ejecutar sin revisar el estado previo.

## Integridad

Cada registro creado por la API se inserta junto con un bloque en la misma
transacción:

- Cadenas independientes: `api-ubuntu` y `api-windows`.
- Génesis: 64 ceros.
- Hash de bloque: SHA-256 en 64 hex, sin prefijo (las columnas son `bpchar(64)`
  y `char(64)`).
- Payload versionado: `canon-v1` para el registro y `block-v1` para el bloque.
- PostgreSQL serializa la cadena con `pg_advisory_xact_lock`; SQL Server usa
  `UPDLOCK, HOLDLOCK`.
- Si la tabla de integridad no existe o es incompatible, el registro se guarda
  y la respuesta indica `unavailable`; no se afirma que esté protegido.

`GET /api/integrity/verify` verifica los bloques, sus hashes y que cada registro
referenciado siga coincidiendo. La tabla es compartida con la aplicación
heredada, por lo que los registros sin bloque se informan como advertencia y no
como fallo. Las cadenas heredadas `ubuntu`/`windows` no se verifican con este
formato.

## Pruebas

```bash
uv run pytest -q                         # unitarias + API, sin bases reales
RUN_DB_INTEGRATION=1 uv run pytest -q    # incluye PostgreSQL y SQL Server
```

Las pruebas de integración escriben dentro de una transacción y terminan siempre
en `ROLLBACK`; no dejan filas. Ver [docs/pruebas.md](docs/pruebas.md).

## Seguridad

- Contraseñas: Argon2id; los hashes bcrypt heredados se rehashean tras un login
  correcto.
- TOTP: secreto cifrado con AES-256-GCM, AAD ligado al usuario; ventana ±30 s y
  contador anti-repetición atómico.
- Sesiones: solo se guarda SHA-256 del token; rotación de `sid`; expiración
  inactiva y absoluta; payload ajeno en la tabla `session` se ignora.
- CSRF: token HMAC ligado al `sid`; comprobación de `Origin` y
  `Sec-Fetch-Site`.
- Bloqueo: intentos fallidos y bloqueo temporal en PostgreSQL; rate limiting por
  IP/cuenta.
- Logs: redacción de contraseñas, tokens, cookies y `Authorization`.
- Cabeceras: `nosniff`, `DENY`, `no-referrer`, `Permissions-Policy`,
  `Cache-Control: no-store` y HSTS en producción.
- `/docs`, `/redoc` y `/openapi.json` desactivados en producción.

Detalles y limitaciones en [docs/seguridad.md](docs/seguridad.md).

## Estructura

```text
app/
  api/            rutas y dependencias HTTP
  core/           configuración, contenedor, seguridad, errores, logging
  models/         modelos de dominio
  repositories/   PostgreSQL y SQL Server (introspección, SQL parametrizado)
  schemas/        contratos Pydantic
  services/       auth, TOTP, sesiones, clima, geocodificación, integridad
docs/             arquitectura, API, seguridad, TLS, datos, privacidad, pruebas
scripts/          inspección de esquemas y reset TOTP
tests/            unitarias, API e integración opt-in
migrations/       vacío: no se ejecuta DDL automático
```

## Documentación

- [Arquitectura](docs/arquitectura.md)
- [API](docs/api.md)
- [Seguridad](docs/seguridad.md)
- [TLS](docs/tls.md)
- [Mapeo de bases de datos](docs/base-de-datos.md)
- [Privacidad](docs/privacidad.md)
- [Pruebas](docs/pruebas.md)
- [Pendientes y acciones manuales](docs/pendientes.md)

## Limitaciones conocidas

- No se validó un login HTTP con una cuenta real porque no se dispone de la
  contraseña de una cuenta de prueba. El flujo completo sí está cubierto con
  servicios reales y repositorios en memoria.
- Los tres usuarios con TOTP heredado requieren reset administrativo.
- El rate limiting es por proceso.
- No hay anclaje externo de la cadena: borrar el último bloque y su registro no
  es detectable solo con la base de datos.
- La tabla de registros es compartida; los registros sin bloque pueden ser
  históricos o de otro proceso.
- El límite de cuerpo se comprueba con `Content-Length`; un proxy debe imponer
  además un límite real.
