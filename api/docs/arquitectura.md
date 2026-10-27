# Arquitectura

## Capas

```text
HTTP (FastAPI)
  api/routes/*        contrato, cookies, CSRF, rate limit
  api/deps.py         sesión, origen, límites, helpers de cookie
        |
Servicios
  AuthService         alta, login, TOTP, inscripción, bloqueo
  SessionService      cookie opaca, payload versionado, rotación
  TOTPService         RFC 6238, QR, cifrado del secreto
  RecordsService      creación/listado combinado, filtros por usuario
  WeatherService      Open-Meteo + caché en memoria
  GeocodingService    Nominatim + caché y throttle
  Integrity*          canonical, hashes, verificación
        |
Repositorios
  Postgres*Repository auth, sesiones, registros, integridad
  SqlServer*Repository registros, integridad
  schema.py           introspección de solo lectura y citado de identificadores
        |
PostgreSQL 18.6 (Ubuntu)     SQL Server 2025 Express (Windows)
```

`app/core/container.py` compone todo. `create_app()` construye el contenedor,
configura logging, middlewares, rutas y el ciclo de vida (cliente HTTP y pools).

## Decisiones

- **Sin DDL**: las tablas existentes se inspeccionan con `information_schema` y
  `sys.columns`; los identificadores se citan y los valores van parametrizados.
- **Tablas compartidas**: PostgreSQL conserva la tabla `session` de la
  aplicación heredada. Solo se interpretan payloads con `v=1`; el resto se
  ignora y no se borra.
- **Cadenas nuevas**: `api-ubuntu` y `api-windows`, separadas de las cadenas
  heredadas `ubuntu`/`windows`, cuyo formato no es verificable.
- **Transacciones**: el registro y su bloque se escriben en la misma conexión y
  transacción. Los pools confirman al salir del contexto; un error revierte.
- **Sincronía**: las rutas que usan psycopg/pyodbc son síncronas y FastAPI las
  ejecuta en su threadpool. Las llamadas a Open-Meteo y Nominatim son `async`
  con `httpx.AsyncClient`.
- **Concurrencia de cadena**: en PostgreSQL se toma un advisory lock
  transaccional por cadena; en SQL Server se usa `UPDLOCK, HOLDLOCK` al leer el
  último bloque.

## Flujo de creación

1. La sesión autenticada aporta `user_id` y `username`.
2. El repositorio traduce el usuario a la clave real de la columna
   `Usuario` (texto o numérica).
3. Se inserta el registro y se obtiene su `Id`.
4. Si integridad está disponible, se calcula el bloque y se inserta en la misma
   transacción.
5. Se confirma y se responde con el registro y el estado de integridad
   (`created`, `disabled` o `unavailable`).

Si la tabla de integridad falta o es incompatible, el registro se guarda y la
respuesta lo declara explícitamente; no se simula protección.

## Disponibilidad

`Container.readiness()` comprueba:

- ping de PostgreSQL y SQL Server;
- introspección de esquemas;
- disponibilidad de la tabla de integridad;
- caché de 3 segundos para no saturar en sondeos.

`status=ok` exige ambos motores y esquemas válidos. `degraded` indica que la API
puede operar pero una capacidad (por ejemplo SQL Server o integridad) no está
disponible. `strict=true` devuelve HTTP 503 si el estado no es `ok`.

## Despliegue

- Un worker es suficiente para desarrollo. Con varios workers, los límites en
  memoria y las cachés son por proceso.
- TLS puede terminar en Uvicorn o en un proxy. En el segundo caso configura
  `TRUSTED_PROXIES` para que `request.client` y `request.url` reflejen el cliente
  y el esquema originales.
- `/docs` se desactiva en producción.
