# Seguridad

## Contraseñas

- Algoritmo actual: Argon2id con `time_cost=3`, `memory_cost=65536`,
  `parallelism=4`, hash de 32 bytes y salt de 16.
- Se aceptan hashes bcrypt heredados (`$2a$`, `$2b$`, `$2y$`); tras un login
  correcto se rehashean a Argon2id.
- Usuario inexistente y cuenta bloqueada ejecutan una verificación señuelo para
  reducir diferencias de tiempo.
- Los hashes nunca se registran ni se devuelven por la API.

## Alta de usuarios

- `POST /api/auth/register` es público, exige un `Origin` permitido y aplica
  límites por IP y por nombre de usuario.
- Solo se aceptan `username` y `password`; cualquier campo extra (`id`, rol,
  TOTP, etc.) se rechaza.
- Política: usuario de 3-64 caracteres y contraseña de 12-128 caracteres con al
  menos tres tipos de caracteres.
- Se guarda únicamente el hash Argon2id; nunca la contraseña.
- La cuenta nace con `totp_enabled=false` y sin secreto. El registro devuelve
  una sesión `pending_enroll`, no una sesión autenticada.
- `REGISTRATION_ENABLED` permite desactivar el alta. Sin valor, está activo en
  desarrollo y desactivado en producción.

## TOTP

- RFC 6238, 6 dígitos, intervalo de 30 s, ventana ±1.
- Secreto aleatorio de PyOTP, cifrado con AES-256-GCM.
- Formato: `v1.<nonce>.<ciphertext>` en base64url.
- AAD: `v1:totp-secret:user:<id>`. Un criptograma no se puede mover a otro
  usuario o propósito.
- Clave separada `TOTP_ENCRYPTION_KEY`; distinta de sesión y registros.
- Anti-repetición: `totp_ultimo_counter` se actualiza con un `UPDATE ... WHERE
  counter > último RETURNING`, atómico.
- Inscripción: el secreto pendiente se guarda cifrado en la sesión; el QR y la
  clave se muestran una vez. Límite de generaciones por hora y de intentos.
- Secretos heredados con otro formato no se descifran: la API responde `503` y
  exige reset administrativo (`scripts/admin_reset_totp.sql`).

## Sesiones

- Token opaco `s1_` + 32 bytes aleatorios.
- En la base solo se guarda SHA-256 del token (hex o UUID según la columna).
- Payload versionado (`v=1`) con estado, usuario, expiraciones y datos de
  inscripción; no contiene el token.
- Expiración inactiva (`SESSION_TTL_SECONDS`) y absoluta
  (`SESSION_ABSOLUTE_TTL_SECONDS`).
- Rotación de `sid` al pasar a autenticado.
- La tabla `session` es compartida: un payload sin `v=1` se ignora y no se
  elimina.
- Logout borra la fila y la cookie.

## CSRF y origen

- Token CSRF = HMAC-SHA256(`SESSION_SECRET_KEY`, `csrf:<sid>`).
- Se compara en tiempo constante.
- Obligatorio en `POST /records`, logout, verify, enroll y confirm.
- `Origin` debe pertenecer a `CORS_ORIGINS` o al mismo origen de la API.
- `Sec-Fetch-Site` debe ser `same-origin`, `same-site` o `none`.
- `SameSite=Lax` por defecto; `None` exige cookies `Secure`.

## Bloqueo y límites

- Intentos fallidos y `bloqueado_hasta` se guardan en PostgreSQL (global).
- Límite de intentos de login y TOTP configurable.
- Rate limiting en memoria por IP y por cuenta (hash del username), ventana
  deslizante de 60 s. El alta usa `RATE_LIMIT_REGISTER_PER_MINUTE` (3 por
  defecto).
- Es **por proceso**: con varios workers cada uno tiene su contador. Para un
  límite global usar Redis o el proxy.
- El bloqueo por cuenta puede ser usado para denegación de servicio; se mitiga
  con el límite por IP y la duración configurable.

## Cookies y cabeceras

- `HttpOnly`, `Secure` en producción, `SameSite` configurable, `Path=/`.
- En producción: nombre `__Host-*` (sin `Domain`, `Path=/`, `Secure`).
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: geolocation=(self)`
- `Cache-Control: no-store` en `/api` y `/health`
- `Strict-Transport-Security` en producción con cookies seguras.
- `X-Request-ID` se acepta o se genera y se devuelve.

## CORS y hosts

- `CORS_ORIGINS` no admite `*` con credenciales.
- Solo métodos `GET`, `POST`, `OPTIONS`; cabeceras `Content-Type`,
  `X-CSRF-Token`, `X-Request-ID`.
- `TrustedHostMiddleware` con `ALLOWED_HOSTS`.

## Documentación y errores

- `/docs`, `/redoc` y `/openapi.json` desactivados en producción (además,
  `DOCS_ENABLED=true` en producción es un error de configuración).
- Los errores de validación no devuelven los valores enviados (pueden contener
  contraseñas o códigos).
- Los errores inesperados devuelven un mensaje genérico y un `request_id`.
- Los logs redactan `password`, `token`, `secret`, `cookie`, `Authorization`,
  `TOTP` y `Bearer <token>`.

## TLS y base de datos

- TLS directo con `SSL_CERTFILE`/`SSL_KEYFILE` o terminación en proxy.
- PostgreSQL: en producción `POSTGRES_SSLMODE` debe ser `require`, `verify-ca` o
  `verify-full`.
- SQL Server: `Encrypt=yes`; `TrustServerCertificate=yes` prohibido en
  producción.
- Contraseñas de bases solo desde `.env`/entorno; no se registran.

## Limitaciones

- Sin anclaje externo, la truncación del final de la cadena no es detectable.
- El límite de cuerpo se basa en `Content-Length`; el proxy debe imponer un
  límite real.
- La autenticación de la API no sustituye la seguridad de la red: usa TLS,
  segmentación y credenciales de base con mínimo privilegio.
- No hay revocación global de sesiones salvo borrar filas de `session` o el
  reset administrativo.
