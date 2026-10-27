# Privacidad y tratamiento de datos

## Datos tratados

- **Cuenta**: `username`, hash de contraseña, secreto TOTP cifrado, estado de
  TOTP, intentos fallidos, bloqueo y fechas de creación.
- **Sesión**: identificador derivado del token (no el token), estado, usuario,
  expiraciones y, durante la inscripción, el secreto TOTP cifrado pendiente.
- **Registros climáticos**: usuario, nombre, apellidos, estado, municipio,
  coordenadas, temperatura, humedad, viento y fecha/hora.
- **Trazabilidad**: logs con `request_id`, sin contraseñas, tokens, cookies ni
  secretos.

La tabla `Georreferencia` es compartida con la aplicación heredada; los datos
históricos no los genera esta API. La API solo añade las filas que recibe por
`POST /api/records`.

## Servicios externos

### Open-Meteo

Se envían latitud, longitud y parámetros meteorológicos. No se envía el usuario,
la sesión ni datos personales. La respuesta se cachea en memoria por coordenadas
redondeadas a 3 decimales durante `WEATHER_CACHE_TTL_SECONDS`.

### Nominatim / OpenStreetMap

Se envían latitud, longitud, idioma y el `User-Agent` configurado. No se envía el
usuario ni la sesión. La respuesta se cachea en memoria por coordenadas
redondeadas a 4 decimales durante `GEOCODING_CACHE_TTL_SECONDS`.

Política de uso:

- máximo aproximado de 1 petición por segundo (`GEOCODING_MIN_INTERVAL_SECONDS`);
- caché activa;
- `GEOCODING_USER_AGENT` debe identificar la aplicación y un contacto real;
- no hacer geocodificación masiva ni usar Nominatim como backend de autocompletado;
- mostrar la atribución `© OpenStreetMap contributors` (la API la devuelve en
  `attribution`).

Open-Meteo no exige atribución en la respuesta, pero se recomienda citar la
fuente en el frontend.

## Cookies

- Cookie de sesión estrictamente necesaria, `HttpOnly`, `Secure` en producción,
  `SameSite=Lax` por defecto.
- No se usan cookies de analítica, publicidad ni seguimiento.
- El frontend no debe leer la cookie; usa los tokens CSRF devueltos por la API.

## Retención

La API no implementa borrado automático de registros ni de usuarios. La
retención depende de la base compartida y debe definirse con el responsable del
sistema. Las sesiones expiradas se eliminan al consultarse o mediante
`delete_expired()` (no hay tarea programada en esta entrega).

## Derechos y acceso

Todos los usuarios autenticados pueden listar todos los registros (requisito
funcional). El filtro `usuario` es opcional. Esto implica que los registros no
están aislados por cuenta; debe documentarse a los usuarios y regularse por
política interna.

## Recomendaciones

- Usar TLS en todo el trayecto.
- Restringir el acceso a las bases por red y credenciales de mínimo privilegio.
- No incluir datos personales en logs ni en mensajes de error.
- Definir una política de retención y un procedimiento de borrado.
- Revisar la licencia y atribución de OpenStreetMap/Nominatim antes de publicar.
- Si se añade analítica en el frontend, hacerlo con consentimiento y fuera de
  esta API.
