# API HTTP

Base: `http://127.0.0.1:8000` (desarrollo). Prefijo de negocio: `/api`.

Formato de error uniforme:

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Credenciales inválidas o sesión no válida",
    "request_id": "6f1c...",
    "details": {}
  }
}
```

Códigos: `400 bad_request`, `401 unauthorized`, `403 forbidden`, `404 not_found`,
`409 conflict`, `413 payload_too_large`, `422 validation_error`,
`429 rate_limited`, `502 upstream_error`, `503 database_unavailable` /
`service_unavailable`, `500 internal_error`.

## Autenticación

### POST `/api/auth/register`

Público y limitado por IP y por nombre de usuario. Crea una cuenta sin TOTP y
devuelve una sesión pendiente de inscripción. No acepta `id`, `usuario` ni
campos de rol. Al no existir una sesión previa, no requiere `X-CSRF-Token`; sí
exige un `Origin` permitido.

```json
{"username": "ana", "password": "Clave-Segura-2026!"}
```

- `username`: 3-64 caracteres; letras, números, punto, guion o guion bajo.
  Debe empezar por letra o número.
- `password`: 12-128 caracteres y al menos tres tipos entre minúsculas,
  mayúsculas, números y símbolos.
- `403`, `422` o `429` no crean usuario.
- `409` si el nombre ya está en uso.
- `403` si `REGISTRATION_ENABLED` está desactivado o el origen no está permitido.

Respuesta `201`:

```json
{
  "status": "enrollment_required",
  "csrf_token": "hex",
  "expires_at": "2026-10-25T18:00:00Z",
  "message": "Cuenta creada. Configure el segundo factor antes de continuar."
}
```

Establece la cookie de sesión pendiente. La cuenta no tiene acceso hasta
completar `POST /api/auth/totp/enroll` y `POST /api/auth/totp/confirm`.

### POST `/api/auth/login`

```json
{"username": "ana", "password": "..."}
```

Respuesta `200`:

```json
{
  "status": "enrollment_required",
  "csrf_token": "hex",
  "expires_at": "2026-10-25T18:00:00Z",
  "message": "Debe configurar el segundo factor antes de continuar"
}
```

`status` es `totp_required` si la cuenta ya tiene TOTP. Establece la cookie de
sesión pendiente.

Errores: `401` credenciales/bloqueo, `403` origen no permitido, `429` límite.

### POST `/api/auth/totp/enroll`

Requiere sesión `pending_enroll` y `X-CSRF-Token`. Devuelve:

```json
{
  "manual_key": "JBSW...",
  "otpauth_uri": "otpauth://totp/...",
  "qr_data_uri": "data:image/png;base64,...",
  "issuer": "Clima API",
  "account": "ana",
  "expires_at": "...",
  "message": "Escanee el código QR..."
}
```

La clave se muestra una única vez. Hay límite de generaciones por hora y de
intentos de confirmación.

### POST `/api/auth/totp/confirm`

```json
{"code": "123456"}
```

Requiere sesión `pending_enroll` y CSRF. Activa TOTP, rota la sesión y devuelve
`status: authenticated`, usuario, nuevo CSRF y expiración.

### POST `/api/auth/totp/verify`

```json
{"code": "123456"}
```

Requiere sesión `pending_totp` y CSRF. Valida ±1 intervalo de 30 s, rechaza
reutilización y rota la sesión.

### POST `/api/auth/logout`

Requiere CSRF si hay sesión. Revoca la sesión y borra la cookie. Responde
`{"status": "logged_out"}`.

### GET `/api/auth/me`

Requiere sesión autenticada. Devuelve usuario, CSRF y expiración:

```json
{
  "user": {"id": 1, "username": "ana", "totp_enabled": true, "created_at": "..."},
  "csrf_token": "hex",
  "session_expires_at": "..."
}
```

## Servicios externos

### GET `/api/weather/current?lat=19.35&lon=-99.16`

Público. Coordenadas en grados decimales. Devuelve temperatura (°C), humedad
relativa (%), viento (km/h), código WMO, condición, hora de observación, zona
horaria y unidades. Si Open-Meteo falla: `502`; si tarda: `502`.

### GET `/api/locations/reverse?lat=19.35&lon=-99.16`

Público. Devuelve `city`, `municipio`, `estado`, `pais`, `country_code`,
`display_name`, `provider: nominatim` y atribución de OpenStreetMap. `404` si no
hay localidad; `502` si el proveedor falla o limita.

## Registros

Todos los endpoints requieren sesión autenticada. Todos los usuarios ven todos
los registros.

### POST `/api/records`

Requiere `X-CSRF-Token`.

```json
{
  "servidor": "ubuntu",
  "nombre": "Ana",
  "paterno": "Pérez",
  "materno": "López",
  "estado": "Ciudad de México",
  "municipio": "Coyoacán",
  "latitud": 19.35,
  "longitud": -99.16,
  "temperatura": 21.5,
  "humedad": 55,
  "viento": 12.3,
  "fecha_hora": "2026-10-25T18:30:45Z"
}
```

- `servidor`: `ubuntu` o `windows`.
- `paterno` es obligatorio para `windows` (columna `NOT NULL`).
- `fecha_hora` es opcional; si falta se usa la hora UTC actual. No puede estar
  en el futuro ni antes de 1900.
- `id` y `usuario` no se aceptan; se derivan de la base y de la sesión.

Respuesta `201`:

```json
{
  "registro": {
    "id": 16,
    "servidor": "ubuntu",
    "usuario": "ana",
    "nombre": "Ana",
    "paterno": "Pérez",
    "materno": "López",
    "estado": "Ciudad de México",
    "municipio": "Coyoacán",
    "latitud": 19.35,
    "longitud": -99.16,
    "temperatura": 21.5,
    "humedad": 55.0,
    "viento": 12.3,
    "fecha_hora": "2026-10-25T18:30:45Z"
  },
  "integridad": {
    "status": "created",
    "cadena": "api-ubuntu",
    "indice": 0,
    "hash_actual": "64 hex"
  }
}
```

`integridad.status`:

- `created`: bloque insertado en la misma transacción.
- `disabled`: `INTEGRITY_ENABLED=false`.
- `unavailable`: tabla ausente/incompatible o bloque no confirmado; incluye
  `detalle`. El registro puede existir sin protección.

### GET `/api/records`

Parámetros:

| Parámetro | Valores | Defecto |
|---|---|---|
| `servidor` | `ubuntu`, `windows`, `ambos` | `ubuntu` |
| `usuario` | nombre exacto | sin filtro |
| `desde`, `hasta` | ISO-8601 | sin límite |
| `limit` | 1-200 | 50 |
| `offset` | 0-100000 | 0 |
| `orden` | `fecha_hora`, `id` | `fecha_hora` |
| `direccion` | `asc`, `desc` | `desc` |

Con `servidor=ambos`, cada fuente aplica `limit`/`offset` por separado y los
resultados se combinan ordenados. `paginacion.per_source=true` lo indica.
`fuentes` informa `status`, `count`, `has_more` y, si aplica, `error`. Si una
fuente falla, `parcial=true`; si fallan ambas, `503`.

### GET `/api/records/{id}?servidor=ubuntu`

Devuelve un registro o `404`. `id` debe ser >= 1.

## Integridad

### GET `/api/integrity/verify?servidor=ambos`

Requiere sesión. Respuesta:

```json
{
  "status": "ok",
  "servidor": "ambos",
  "sources": {
    "ubuntu": {
      "servidor": "ubuntu",
      "status": "ok",
      "bloques_verificados": 3,
      "registros_verificados": 3,
      "registros_sin_bloque": 12,
      "errores": [],
      "advertencias": ["12 registro(s) sin bloque de integridad..."],
      "detalle": null
    }
  }
}
```

`status` global: `ok`, `empty` (sin bloques), `invalid`, `partial`,
`unavailable`, `disabled`. Cada fuente puede ser `ok`, `empty`, `invalid`,
`unavailable`, `disabled` o `error`.

`registros_sin_bloque` no invalida la cadena: la tabla es compartida y puede
contener filas históricas o de otro proceso. Los errores de hash, secuencia,
registro referenciado o datos alterados sí la invalidan.

## Salud

- `GET /health/live`: `{"status": "ok", "service": "Clima API"}`.
- `GET /health/ready`: estado de PostgreSQL, SQL Server, esquemas, sesiones e
  integridad. `?strict=true` responde `503` si no es `ok`.

## Cookies y CSRF

- Cookie de sesión opaca, `HttpOnly`, `Secure` en producción, `SameSite=Lax`
  (configurable), `Path=/`; en producción se usa el prefijo `__Host-`.
- El token CSRF se envía en el cuerpo de login, verify, confirm y `/me`.
- Las escrituras (`POST`) requieren `X-CSRF-Token`.
- Se valida `Origin` contra `CORS_ORIGINS` y el mismo origen de la API, además
  de `Sec-Fetch-Site`.
