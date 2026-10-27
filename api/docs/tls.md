# TLS y despliegue seguro

En producción la API debe servirse **solo por HTTPS**. Las cookies se marcan
`Secure` automáticamente y el nombre cambia a `__Host-clima_session`.

## Opción A: TLS en Uvicorn

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -nodes -days 365 \
  -keyout certs/dev-key.pem -out certs/dev-cert.pem \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

`.env`:

```dotenv
APP_ENV=production
DOCS_ENABLED=false
POSTGRES_SSLMODE=require
SSL_CERTFILE=/ruta/api/certs/dev-cert.pem
SSL_KEYFILE=/ruta/api/certs/dev-key.pem
SESSION_SECURE_COOKIES=true
ALLOWED_HOSTS=["localhost","127.0.0.1"]
```

```bash
uv run python -m app
curl -k https://127.0.0.1:8000/health/live
```

Un certificado autofirmado sirve para pruebas, no para usuarios reales. Para
producción usa Let's Encrypt o un certificado corporativo.

## Opción B: proxy inverso (recomendado)

Uvicorn escucha en `127.0.0.1:8000` y el proxy termina TLS.

```dotenv
APP_ENV=production
DOCS_ENABLED=false
POSTGRES_SSLMODE=require
API_HOST=127.0.0.1
API_PORT=8000
TRUSTED_PROXIES=["127.0.0.1"]
SESSION_SECURE_COOKIES=true
ALLOWED_HOSTS=["clima.example.org"]
CORS_ORIGINS=["https://clima.example.org"]
SSL_CERTFILE=
SSL_KEYFILE=
```

`TRUSTED_PROXIES` activa `proxy_headers` y `forwarded_allow_ips` en Uvicorn, de
modo que `request.url.scheme`, `request.url.netloc` y `request.client` reflejen
la petición original. No incluyas rangos amplios: solo la IP del proxy.

### Caddy

```caddyfile
clima.example.org {
    encode gzip
    reverse_proxy 127.0.0.1:8000
}
```

Caddy obtiene y renueva el certificado y envía `X-Forwarded-*`.

### nginx

```nginx
server {
    listen 443 ssl http2;
    server_name clima.example.org;

    ssl_certificate     /etc/letsencrypt/live/clima.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/clima.example.org/privkey.pem;

    client_max_body_size 1m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }
}

server {
    listen 80;
    server_name clima.example.org;
    return 301 https://$host$request_uri;
}
```

`client_max_body_size 1m` complementa el límite de `Content-Length` de la API.

## Comprobaciones

```bash
curl -sS https://clima.example.org/health/ready | jq
curl -sSI https://clima.example.org/api/records
```

Debe aparecer:

- `Strict-Transport-Security` (solo producción con cookies seguras),
- `Set-Cookie` con `Secure`, `HttpOnly`, `SameSite=Lax` y `Path=/`,
- `Cache-Control: no-store`,
- `/docs` en `404`.

## Certificados

- Nunca versionar `certs/`, `*.key`, `*.pem`, `*.p12` ni `*.pfx` (`.gitignore`).
- Renovación: `certbot renew` o Caddy automático; recargar el proxy tras renovar.
- Si usas TLS en Uvicorn, reinicia el proceso para cargar el certificado nuevo.

## Base de datos

- PostgreSQL: `POSTGRES_SSLMODE=require` o `verify-full` en producción. La
  configuración rechaza `disable`, `allow`, `prefer`.
- SQL Server: `SQLSERVER_ENCRYPT=yes` y
  `SQLSERVER_TRUST_SERVER_CERTIFICATE=no` en producción.
- Mantén las contraseñas en `.env` con permisos `600` o en un gestor de
  secretos; nunca en el repositorio.
