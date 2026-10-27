# Mapeo de bases de datos

La API **no crea, altera ni renombra tablas**. Solo lee metadatos y ejecuta DML
parametrizado sobre las tablas existentes. `migrations/` está vacío a propósito.

## PostgreSQL (`192.168.56.10:5432/UPP`)

### `usuarios`

| Columna | Tipo observado | Uso |
|---|---|---|
| `id` | `int4`, secuencia | identificador |
| `username` | `varchar(150)` | login |
| `password_hash` | `varchar(255)` | Argon2id/bcrypt |
| `totp_secret_encrypted` | `text` | secreto cifrado `v1.` o legado |
| `totp_enabled` | `bool` | segundo factor activo |
| `created_at` | `timestamp` | informativo |
| `intentos_fallidos` | `int4` | bloqueo |
| `bloqueado_hasta` | `timestamptz` | bloqueo |
| `totp_ultimo_counter` | `int8` | anti-repetición |

`POST /api/auth/register` inserta una fila en `usuarios` con
`password_hash` Argon2id, `totp_enabled=false`, sin secreto y con los contadores
de bloqueo a cero. La unicidad de `username` la garantiza
`usuarios_username_key`.

### `session`

| Columna | Tipo | Uso |
|---|---|---|
| `sid` | `varchar` | SHA-256 del token |
| `sess` | `jsonb` | payload versionado |
| `expire` | `timestamptz` | expiración inactiva |

La tabla es compartida con la aplicación heredada. Solo se interpretan payloads
con `v=1`; una fila con claves como `etapa`, `cookie`, `usuario` o `csrfToken`
se ignora y **no se borra**.

### `Georreferencia`

| Columna | Tipo observado |
|---|---|
| `Usuario` | texto (se detecta si fuera numérico) |
| `Nombre` | texto |
| `Paterno`, `Materno` | texto, nullable |
| `Estado`, `Municipio` | texto |
| `Latitud`, `Longitud` | `numeric(10,7)` |
| `Temperatura`, `Humedad` | `numeric(5,2)` |
| `Viento` | `numeric(6,2)` |
| `Id` | `int4`, `nextval` |
| `FechaHora` | `timestamp` (sin zona) |

### `cadena_bloques`

| Columna | Tipo | Uso |
|---|---|---|
| `cadena` | `varchar(32)` | `api-ubuntu` |
| `indice` | entero | secuencia desde 0 |
| `datos` | `jsonb` | JSON canónico `canon-v1` |
| `registro_id` | `int8` | `Georreferencia.Id` |
| `hash_anterior` | `bpchar(64)` | 64 hex o génesis |
| `hash_actual` | `bpchar(64)` | 64 hex |
| `creado_en` | `timestamp` | UTC naive |

La cadena heredada `ubuntu` (2 bloques) no se mezcla ni se verifica.

## SQL Server (`192.168.56.11:49834/UPP`)

Driver: `ODBC Driver 18 for SQL Server`.

### `dbo.Georreferencia`

| Columna | Tipo | Notas |
|---|---|---|
| `Id` | `int IDENTITY` | `OUTPUT INSERTED.Id` |
| `Usuario` | `varchar(100)` | `NOT NULL` |
| `Nombre` | `varchar(100)` | `NOT NULL` |
| `Paterno` | `varchar(100)` | `NOT NULL` |
| `Materno` | `varchar(100)` | nullable |
| `Estado`, `Municipio` | `varchar` | nullable |
| `Latitud`, `Longitud` | `decimal(10,7)` | |
| `Temperatura`, `Humedad` | `decimal(5,2)` | |
| `Viento` | `decimal(7,2)` | |
| `FechaHora` | `datetime2(7)` | `NOT NULL` |

`Paterno` obliga a validar `paterno` en la API cuando `servidor=windows`.

### `dbo.CadenaBloques`

| Columna | Tipo | Uso |
|---|---|---|
| `Cadena` | `varchar(32)` | `api-windows` |
| `Indice` | entero | secuencia desde 0 |
| `RegistroId` | entero | `Georreferencia.Id` |
| `Datos` | `nvarchar(max)` | JSON canónico |
| `HashAnterior` | `char(64)` | 64 hex |
| `HashActual` | `char(64)` | 64 hex |
| `CreadoEn` | `datetime2(3)` | UTC naive |

## Reglas comunes

### Identificadores

- Se citan siempre: `"Nombre"` en PostgreSQL y `[Nombre]` en SQL Server.
- Los valores van como parámetros (`%s` o `?`), nunca interpolados.
- Los nombres de tabla/columna provienen de la introspección, no del cliente.

### Usuario

- Si la columna `Usuario` es numérica, se guarda `usuarios.id`.
- Si es texto, se guarda `username`.
- En listados, el filtro `usuario` se traduce al mismo valor; si el usuario no
  existe en PostgreSQL, la fuente devuelve vacío sin consultar la tabla.

### Fechas

- Se normalizan a UTC.
- Columnas `timestamp`/`datetime2` (sin zona) reciben UTC **naive** para evitar
  conversiones dependientes del `TimeZone` del servidor.
- Las lecturas se devuelven como UTC aware.
- `timestamptz`/`datetimeoffset` conservan el offset y se normalizan a UTC.

### Integridad

- Cadenas nuevas independientes; génesis 64 ceros.
- Hash SHA-256 hex de 64 caracteres, sin prefijo, por las columnas `char(64)`.
- `datos` guarda el JSON canónico del registro, incluido `usuario`.
- El bloque se inserta en la misma transacción que el registro.
- Si la tabla falta o es incompatible, la API responde `unavailable` y no
  asegura integridad.
- Los registros históricos o de otros procesos no tienen bloque; se informan
  como `registros_sin_bloque`.

### Secuencias

Las pruebas de integración hacen `ROLLBACK`, pero PostgreSQL y SQL Server no
revocan los valores de secuencia/identity. Tras las pruebas, PostgreSQL quedó en
`22` y SQL Server en `1013`; no quedaron filas nuevas.
