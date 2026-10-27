# Pendientes y acciones manuales

## Bloqueos actuales

### 1. Login real con una cuenta existente

El alta con `POST /api/auth/register` se validó de extremo a extremo contra
PostgreSQL con una cuenta temporal, inscripción TOTP, `GET /api/auth/me` y
logout; después se eliminaron el usuario y sus sesiones. El alta también está
cubierta por pruebas con repositorios en memoria.

Lo que falta es validar `POST /api/auth/login` con la contraseña de una cuenta
preexistente que ya tenga TOTP. **Acción manual**: usar una cuenta de staging con
contraseña conocida o crear una desde `/register` y conservarla para la prueba.

### 2. Usuarios con TOTP heredado

Hay 3 usuarios con `totp_enabled=true` y secretos en un formato que esta API no
puede descifrar (no empiezan por `v1.`). No se validó su login real por falta de
credenciales; con el formato actual, la verificación TOTP devuelve `503` y el
acceso queda bloqueado hasta el reset administrativo.

**Acción manual** (por usuario; primero dry-run):

```bash
uv run python scripts/admin_reset_totp.py --username NOMBRE
uv run python scripts/admin_reset_totp.py --username NOMBRE --apply
```

Alternativa con `psql` (si está instalado):

```bash
psql "host=192.168.56.10 dbname=UPP user=tux" \
  -v username='NOMBRE' -f scripts/admin_reset_totp.sql
```

Ambos desactivan TOTP, borran el secreto, limpian bloqueos y revocan sesiones de
esta API. El usuario deberá inscribir TOTP de nuevo. Ambos abortan si el nombre
no existe o no es único.

### 3. Validación del script SQL de reset

En este host no está instalado el cliente `psql`, por lo que
`scripts/admin_reset_totp.sql` no se ejecutó contra la base. La variante Python
`scripts/admin_reset_totp.py` sí se probó en modo dry-run con el usuario `admin`
y con un usuario inexistente (código de salida 2, sin cambios).

**Acción manual**: instalar `postgresql` (cliente) y probar el script SQL en una
base de staging antes de usarlo en producción, o usar la variante Python.

### 4. Cadenas de integridad nuevas vacías

No hay bloques `api-ubuntu` ni `api-windows` porque todavía no se creó ningún
registro a través de la API en las tablas reales. `GET /api/integrity/verify`
devuelve `empty` hasta el primer registro.

**Acción**: crear un registro con una cuenta válida y volver a verificar. No es
un fallo.

## Acciones manuales recomendadas

### Driver ODBC

El driver de Microsoft está extraído localmente. Si se mueve de host o se
reinstala el sistema:

1. Instalar `unixodbc`.
2. Instalar/extractar `ODBC Driver 18 for SQL Server`.
3. Ajustar `ODBC_CONFIG_DIR` o dejar el driver en `/etc/odbcinst.ini`.
4. Verificar:

```bash
uv run python -c "from app.core.config import get_settings; from app.repositories.pool import SqlServerManager; print(SqlServerManager(get_settings()).driver_missing)"
```

### TLS

Generar certificados o configurar Caddy/nginx. Activar
`APP_ENV=production`, `SESSION_SECURE_COOKIES=true`, `ALLOWED_HOSTS` y
`CORS_ORIGINS`. Ver `docs/tls.md`.

### Secretos

- Rotar las tres claves antes de producción si el `.env` actual se compartió.
- Rotar contraseñas de base si se expusieron.
- Permisos `600` para `.env`.
- No versionar `.env`, certificados ni claves.

### Base de datos

- Revisar privilegios: la API necesita `SELECT/INSERT/UPDATE/DELETE` en
  `usuarios`, `session`, `Georreferencia` y `cadena_bloques`/`CadenaBloques`.
  No necesita DDL.
- Confirmar que las cadenas `api-*` no colisionan con otros procesos.
- Definir retención y borrado de datos.
- Programar limpieza de sesiones expiradas (`SessionService.delete_expired()` no
  tiene tarea programada).

### Operación

- Rate limiting global si hay varios workers (Redis/proxy).
- Backups de ambas bases.
- Monitoreo de `/health/ready` y de `GET /api/integrity/verify`.
- Alertar si `status` de integridad pasa a `invalid`.
- Revisar logs por `request_id` sin incluir secretos.

## Limitaciones de diseño aceptadas

- Sin anclaje externo, la truncación del final de la cadena no es detectable.
- La tabla de registros es compartida; los registros sin bloque se informan como
  advertencia, no como error.
- El límite de cuerpo depende de `Content-Length`; el proxy debe imponer un
  límite real.
- La API no implementa DDL ni migraciones.
- El frontend está en `web/` y el alta de usuarios se controla con
  `REGISTRATION_ENABLED`. No hay panel administrativo, roles, recuperación de
  contraseña ni baja de cuentas.
- Las cadenas heredadas `ubuntu`/`windows` no se verifican con el formato
  `canon-v1`/`block-v1`.
