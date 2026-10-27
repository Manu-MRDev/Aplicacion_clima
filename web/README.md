# Clima Web

Frontend React + TypeScript para la API FastAPI de Clima. Consume el contrato
real de `api/docs/api.md` para autenticación con contraseña y TOTP, consulta
meteorológica, registros en PostgreSQL/SQL Server e integridad de las cadenas.

No incluye un backend alternativo, no escribe fuera de los endpoints existentes
y no calcula hashes en el navegador.

## Requisitos

- Node.js `^20.19.0` o `>=22.12.0` y npm (requisito de Vite 8).
- Backend Clima API disponible (por defecto en `http://localhost:8000`).
- Puedes crear una cuenta desde `/register` si el backend tiene habilitado
  `REGISTRATION_ENABLED` (activo en desarrollo por defecto).
- Para entrar con una cuenta existente, debe permitir el flujo de inscripción o
  tener un segundo factor configurado.

## Puesta en marcha

```bash
cd web
cp .env.example .env
npm install
npm run dev
```

El frontend queda en `http://localhost:5173`. Vite usa `host: "localhost"`,
`port: 5173` y `strictPort: true` de forma deliberada: el backend de desarrollo
solo admite ese origen exacto en `CORS_ORIGINS`.

`.env.example` contiene únicamente:

```env
VITE_API_BASE_URL=http://localhost:8000
```

El archivo `.env` real está excluido por `.gitignore`. No deben colocarse
contraseñas, secretos TOTP, cookies, tokens CSRF ni claves del backend en
variables `VITE_*`: cualquier valor `VITE_*` termina incluido en el bundle.

### Backend y CORS

En el directorio `api`, el backend debe estar ejecutándose en el puerto 8000 y
su entorno debe incluir el origen exacto del frontend:

```env
CORS_ORIGINS=["http://localhost:5173"]
ALLOWED_HOSTS=["localhost","127.0.0.1","testserver"]
```

Abre el frontend con `localhost`, no con `127.0.0.1`, salvo que también añadas
ese origen a `CORS_ORIGINS`. El navegador envía las cookies con
`credentials: "include"`; por eso el backend no puede usar `*` en CORS.

Comprobaciones rápidas del backend:

```bash
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready
curl -i http://localhost:8000/api/weather/current?lat=19.4326&lon=-99.1332
```

## Scripts

| Comando | Descripción |
|---|---|
| `npm run dev` | Servidor Vite de desarrollo en `http://localhost:5173`. |
| `npm run typecheck` | Comprobación estricta de TypeScript sin emitir archivos. |
| `npm test` | Suite Vitest/JSDOM de una sola ejecución. |
| `npm run test:watch` | Vitest en modo interactivo. |
| `npm run test:coverage` | Cobertura con el proveedor V8. |
| `npm run build` | Typecheck y compilación de producción en `dist/`. |
| `npm run preview` | Vista local del bundle compilado en el puerto 4173. |

`preview` no es un servidor de producción y su puerto no está incluido en el CORS
de desarrollo. Para probar el bundle contra el backend, usa un proxy inverso del
mismo origen o configura el backend expresamente.

## Funcionalidad

### Autenticación

1. `/register` permite crear una cuenta con usuario, contraseña y confirmación.
   La validación local reproduce la política del backend: usuario de 3-64
   caracteres y contraseña de 12-128 con al menos tres tipos de caracteres.
2. `POST /api/auth/register` crea la cuenta y devuelve una sesión pendiente de
   inscripción. La interfaz continúa directamente con el QR de TOTP. Si el
   backend tiene el registro desactivado, muestra su mensaje sin inventar éxito.
3. `POST /api/auth/login` con usuario y contraseña.
4. Si el backend responde `totp_required`, se solicita el código de seis dígitos
   y se llama a `POST /api/auth/totp/verify` con el CSRF de la sesión pendiente.
5. Si responde `enrollment_required`, se llama a
   `POST /api/auth/totp/enroll`; el QR y la clave manual se muestran una sola vez
   y no se guardan. Después se confirma con
   `POST /api/auth/totp/confirm`.
6. Al iniciar la aplicación se consulta `GET /api/auth/me`. El estado de sesión
   vive en memoria: al recargar la página se vuelve a comprobar contra el
   backend.
7. Un `401` en una ruta privada emite un evento global, limpia la sesión y
   redirige al login con el aviso de sesión terminada.
8. `POST /api/auth/logout` envía el CSRF, revoca la sesión y vuelve al login.

Las contraseñas, el código TOTP, la clave de inscripción, el CSRF y la cookie de
sesión no se escriben en `localStorage` ni `sessionStorage`. La cookie es
`HttpOnly` y la gestiona el navegador.

### Panel meteorológico

- No consulta el clima automáticamente al entrar.
- Obtiene la ubicación solo al pulsar “Usar mi ubicación”; si se rechaza el
  permiso, lo explica y permite introducir coordenadas manuales.
- `GET /api/weather/current` devuelve el clima actual de Open-Meteo.
- `GET /api/locations/reverse` devuelve la localidad mediante Nominatim. Si esta
  segunda llamada falla, el clima y las coordenadas siguen visibles y se muestra
  una advertencia de resultado parcial. No se inventan ciudad, estado ni
  municipio.
- Los valores ausentes se muestran como `—`, nunca como ceros.
- “Guardar estos datos” precarga el formulario con las mediciones reales, la
  hora de observación y la ubicación disponibles; el guardado exige revisar y
  confirmar el formulario.

### Registros

- `POST /api/records` envía `servidor: "ubuntu" | "windows"`, los datos de la
  observación y el encabezado `X-CSRF-Token`.
- El frontend no envía `usuario` ni `id`: el backend los deriva de la sesión.
- El apellido paterno es obligatorio cuando el destino es SQL Server (Windows),
  tal como exige el backend.
- Antes de guardar se muestra un diálogo con el servidor de destino y el usuario
  autenticado. El resultado solo se presenta como correcto después de que el
  backend confirma la creación y devuelve el bloque de integridad.
- Se distinguen `created`, `disabled` y `unavailable`: un registro guardado sin
  bloque confirmado no se presenta como “integridad confirmada”.
- El historial consulta `GET /api/records?servidor=ambos` y muestra el origen en
  cada fila, porque los IDs solo son únicos dentro de cada servidor.
- La paginación combinada es por fuente: `limit` y `offset` se aplican por
  separado en PostgreSQL y SQL Server; no representa un total global.
- Si una fuente falla, se muestra `parcial=true`, el estado de cada fuente y los
  registros de la fuente disponible. Si fallan ambas, se muestra el error sin
  filas inventadas.
- El detalle usa `GET /api/records/{id}?servidor=...`; nunca busca un ID solo,
  porque puede existir en ambos servidores.
- Filtros disponibles: servidor, usuario exacto, rango de fechas, límite,
  orden y dirección. La tabla permite ordenar por ID o fecha/hora.

### Integridad

- La página empieza en un estado neutral: no afirma que la cadena sea válida
  antes de ejecutar `GET /api/integrity/verify`.
- La verificación se ejecuta solo por acción del usuario y puede hacerse sobre
  ambos servidores o sobre uno.
- `ok` se muestra como cadena válida; `empty` como “sin bloques todavía” y no
  como éxito; `invalid`, `partial`, `unavailable` y `disabled` tienen
  presentaciones distintas.
- Los registros sin bloque se muestran como advertencia, no como invalidación.
  Los errores de hash, secuencia o contenido se muestran como errores.
- Si una fuente falla en una verificación combinada, el resultado global es
  parcial y se identifica la fuente no disponible.

## Comandos de voz

El dictado solo reconoce órdenes de guardado, por ejemplo:

- “Guardar en servidor 1”
- “Guardar en servidor 2”
- “Guardar en Ubuntu”
- “Guardar en Windows”

“Servidor 1” corresponde a PostgreSQL/Ubuntu y “servidor 2” a SQL
Server/Windows. Si la frase menciona ambos servidores o es ambigua, no se
selecciona ninguno. Las órdenes de consulta, como “consultar el clima”, no se
interpretan como guardado.

El reconocimiento nunca guarda por sí solo: rellena el destino y abre el mismo
diálogo de confirmación. El micrófono se detiene al obtener un resultado, al
producirse un error, a los 12 segundos o al desmontar el componente. No hay
escucha continua.

Limitaciones reales:

- Depende de `SpeechRecognition`/`webkitSpeechRecognition`, disponible
  principalmente en navegadores Chromium y en contextos seguros (HTTPS o
  `localhost`).
- El navegador o el proveedor del servicio de voz puede enviar el audio a sus
  servidores; no se usa para datos sensibles.
- La precisión depende del idioma, del micrófono y del ruido. El formulario
  siempre se puede usar sin voz.

## Seguridad y manejo de errores

- Todas las peticiones pasan por `src/services/apiClient.ts`; no hay `fetch`
  sueltos en componentes.
- Se usa `credentials: "include"`, `cache: "no-store"` y un tiempo máximo de
  espera de 15 segundos. Los timeouts se distinguen de los errores de red.
- Los mensajes de error usan el mensaje seguro del backend o un texto genérico;
  no se muestran trazas, SQL, rutas internas ni detalles de infraestructura.
- Los estados de carga, vacío, error, parcial, sesión expirada y servicio no
  disponible tienen representación explícita.
- Las rutas privadas redirigen al login conservando el destino de vuelta.
- La geolocalización no se consulta hasta que el usuario la solicita.
- No se incluyen datos meteorológicos ni ubicaciones de ejemplo: toda cifra
  mostrada proviene de una respuesta de la API.
- En producción, el alta pública está desactivada por defecto en el backend.
  Si no deseas registro abierto, deja `REGISTRATION_ENABLED=false`; la interfaz
  mostrará el mensaje seguro del backend si alguien intenta crear una cuenta.

## Estructura

```text
src/
  components/      UI, autenticación, clima y registros
  contexts/        sesión, CSRF y estado de autenticación
  hooks/           consulta de clima, registros, geolocalización y voz
  pages/           panel, login, alta de cuenta, historial, nuevo registro e integridad
  routes/          rutas protegidas y navegación
  services/        cliente HTTP y servicios por dominio
  styles/          sistema visual responsive
  tests/           pruebas con Vitest, Testing Library y fetch simulado
  types/           contrato TypeScript de la API
  utils/           validación, fechas, errores y comandos de voz
```

## Pruebas

```bash
npm run typecheck
npm test
npm run build
```

La suite cubre el cliente HTTP (incluidos CSRF, timeout y cancelación), el
registro de cuentas, el flujo de login/TOTP/inscripción, la expiración de
sesión, el panel meteorológico, la precarga del formulario, la creación y
confirmación de registros, los comandos de voz, los filtros y la paginación del
historial, los resultados parciales, la verificación de integridad, la
navegación y el almacenamiento seguro.

Las pruebas de interfaz usan un `fetch` simulado y no escriben en las bases de
datos reales. La validación contra un backend real requiere que el alta esté
habilitada o una cuenta existente; puedes crear una desde `/register`. No se
incluyen credenciales en el repositorio.

## Producción

### Opción recomendada: mismo origen con proxy inverso

Sirve el contenido de `dist/` y reenvía `/api` al backend FastAPI bajo el mismo
origen. Así la cookie `__Host-clima_session` y `SameSite=Lax` funcionan sin CORS
y el frontend no necesita un origen separado.

```nginx
server {
    listen 443 ssl;
    server_name clima.example.org;

    ssl_certificate     /ruta/fullchain.pem;
    ssl_certificate_key /ruta/privkey.pem;

    root /srv/clima-web/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health/ {
        proxy_pass http://127.0.0.1:8000;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Compila con la URL vacía para usar el mismo origen:

```bash
VITE_API_BASE_URL= npm run build
```

El backend debe ejecutarse con, como mínimo:

```env
APP_ENV=production
SESSION_SECURE_COOKIES=true
DOCS_ENABLED=false
ALLOWED_HOSTS=["clima.example.org"]
CORS_ORIGINS=["https://clima.example.org"]
```

Y con TLS real. El backend cambia la cookie a `__Host-clima_session`, que exige
`Secure`, `Path=/` y HTTPS. No sirvas la aplicación de producción por HTTP ni
uses `vite preview` como servidor final.

### Frontend y API en orígenes distintos

Si no puedes usar el mismo origen, compila con la URL exacta del backend:

```bash
VITE_API_BASE_URL=https://api.example.org npm run build
```

Añade `https://clima.example.org` a `CORS_ORIGINS` y permite credenciales. Las
cookies de sesión de terceros pueden ser bloqueadas por el navegador; el proxy
del mismo origen es más robusto y es la opción recomendada.

## Limitaciones de integración conocidas

- No existe un endpoint de búsqueda directa de ciudades. La ubicación se obtiene
  por geolocalización o coordenadas y la localidad se resuelve con
  geocodificación inversa.
- El alta pública puede desactivarse en el backend con
  `REGISTRATION_ENABLED=false`; en producción queda desactivada por defecto.
- El alta no verifica el correo ni ofrece recuperación de contraseña. No hay
  panel de administración, roles ni eliminación de cuentas desde la interfaz.
- La verificación real de login/TOTP y la inserción de registros requieren una
  cuenta autorizada y acceso a las bases de datos de integración. Las pruebas
  automatizadas no tocan esos sistemas.
- El backend no está incluido en este directorio; el frontend depende de que ya
  esté configurado y en ejecución.
- Los IDs se repiten entre servidores; cualquier integración nueva debe enviar
  siempre `servidor` al consultar un registro.
- La paginación combinada es por fuente y no ofrece un total global.
- Las cadenas heredadas llamadas `ubuntu` y `windows` no se verifican con el
  formato de las cadenas nuevas de la API.

## Solución de problemas

- **403 al iniciar sesión o guardar**: el `Origin` no coincide con
  `CORS_ORIGINS`, o se abrió `127.0.0.1` en vez de `localhost`.
- **401 tras recargar**: la cookie no llegó al backend por un origen/puerto
  distinto o por una política de cookies del navegador.
- **La sesión se cierra**: el backend devolvió `401`; el frontend limpia el
  estado y muestra el aviso de sesión terminada.
- **El micrófono no aparece**: el navegador no implementa Web Speech API, no es
  un contexto seguro o se denegó el permiso. Usa el formulario manual.
- **El clima falla pero la página responde**: revisa `/health/ready` y los
  límites de Open-Meteo/Nominatim; el frontend no sustituye datos externos.
