# Pruebas

## Comandos

```bash
# Unitarias y API (sin bases reales)
uv run pytest -q

# Incluye PostgreSQL y SQL Server reales
RUN_DB_INTEGRATION=1 uv run pytest -q

# Solo integración, con detalle
RUN_DB_INTEGRATION=1 uv run pytest -q tests/integration -vv
```

`tests/integration` está marcado con `@pytest.mark.integration` y se omite si
`RUN_DB_INTEGRATION` no es `1`.

## Cobertura

### Unitarias

- **Crypto**: AES-256-GCM, nonce aleatorio, AAD por usuario, manipulación,
  versiones y claves de 32 bytes.
- **Seguridad**: Argon2id, bcrypt heredado con rehash, tokens de sesión, SHA-256
  del `sid`, CSRF, comparación en tiempo constante, redacción de logs.
- **TOTP**: códigos actuales, ventana ±1, formato, reutilización, URI, QR y
  cifrado ligado al usuario.
- **Integridad**: normalización de texto/decimales/fechas, JSON canónico, hash de
  registro y bloque, cadena válida, datos/hash alterados, saltos de índice,
  registros inexistentes y `hash_anterior` nulo fuera del génesis.
- **Sesiones**: creación, lectura, payload ajeno, expiración, renovación,
  rotación, revocación y `sid` UUID.
- **Auth**: alta de usuarios (incluido duplicado y registro deshabilitado),
  usuario inexistente, contraseña incorrecta, bloqueo, login con y sin TOTP,
  reutilización, secreto legado, inscripción completa, límites y expiración de
  la verificación de contraseña.
- **Registros**: estados de integridad, usuario numérico/texto, listado simple y
  combinado, orden, fuente parcial y filtro por usuario.
- **Clima/geocodificación**: éxito, caché, timeout, HTTP 4xx/5xx, JSON inválido,
  campos faltantes, códigos WMO desconocidos y atribución.
- **API**: flujo completo login → inscripción → confirmación → `/me` → logout,
  TOTP existente, CSRF, origen, rate limit, validación sin eco de contraseña,
  registros, integridad, salud, docs, CORS y cabeceras.
- **Configuración**: claves distintas, base64 de 32 bytes, producción, TLS,
  cookies, CORS y listas.

### Integración real

`tests/integration/test_databases.py`:

1. `readiness` real: PostgreSQL y SQL Server `up`, esquemas `ok`.
2. Listado real en PostgreSQL.
3. Alta real de usuario en PostgreSQL, dentro de una transacción, con
   `ROLLBACK`; comprueba el hash Argon2id y que no queda la fila.
4. Listado real en SQL Server.
5. Inserción PostgreSQL + bloque + hash canónico, dentro de una transacción, y
   `ROLLBACK`; comprueba que el registro y el bloque no persisten.
6. Lo mismo en SQL Server, usando `OUTPUT INSERTED.Id`.
7. Verificación de integridad de ambas cadenas.

Las conexiones de escritura usan un manager de una sola conexión que **no
confirma**. Al final se ejecuta `ROLLBACK` y se verifica el conteo por `Id`.

## Resultados reales

Ejecutados en este host (2026-10-25):

```text
uv run pytest -q
235 passed, 7 skipped in 12.70s

RUN_DB_INTEGRATION=1 uv run pytest -q tests/integration
7 passed in 3.89s

RUN_DB_INTEGRATION=1 uv run pytest -q
242 passed in 14.74s
```

Readiness real:

```json
{
  "status": "ok",
  "checks": {
    "postgresql": {"status": "up"},
    "sqlserver": {"status": "up"},
    "postgresql_schema": {"status": "ok"},
    "session_store": {"status": "ok"},
    "sqlserver_schema": {"status": "ok"}
  },
  "integrity": {
    "enabled": true,
    "postgres": "available",
    "sqlserver": "available"
  }
}
```

Integridad real:

```json
{
  "status": "empty",
  "sources": {
    "ubuntu": {"status": "empty", "bloques_verificados": 0, "registros_sin_bloque": 12},
    "windows": {"status": "empty", "bloques_verificados": 0, "registros_sin_bloque": 6}
  }
}
```

No hay bloques `api-*` todavía. Los 12 y 6 registros heredados no tienen bloque y
se informan como advertencia.

Tras las pruebas con rollback:

- PostgreSQL: 12 filas, `max(Id)=15`, secuencia `22`.
- SQL Server: 6 filas, `max(Id)=1006`, `IDENT_CURRENT=1013`.
- Bloques `api-%`: 0 en ambos.

Las secuencias no se revierten con `ROLLBACK`; es el único efecto observable.

## Lo que no está cubierto

- Login HTTP real con una cuenta existente: no se dispone de contraseña de
  aplicación ni de un usuario de prueba. El flujo está cubierto con los servicios
  reales y repositorios en memoria.
- Inscripción TOTP con una aplicación autenticadora física: se validó el código
  generado por PyOTP, no un teléfono.
- Carga con varios workers y rate limiting global (el limitador es por proceso).
- TLS con un certificado público real.
- Borrado/truncación de la cadena más allá de los casos unitarios.

## Cómo añadir una prueba E2E real

1. Crear una cuenta de prueba con `POST /api/auth/register` (o insertarla en
   PostgreSQL) con una contraseña conocida y sin TOTP.
2. Ejecutar la API con TLS o en `127.0.0.1`.
3. Hacer login, inscribir TOTP, confirmar, crear un registro, listarlo, verificar
   integridad y logout.
4. Limpiar el usuario, sus sesiones, y los registros/bloques creados por la
   prueba (o ejecutar todo contra una base de staging).

No usar datos de producción para pruebas destructivas.
