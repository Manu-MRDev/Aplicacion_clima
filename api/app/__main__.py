"""Ejecución local con TLS opcional: ``python -m app``."""

from __future__ import annotations

import uvicorn

from app.core.config import get_settings
from app.main import create_app


def main() -> None:
    settings = get_settings()
    app = create_app(settings)
    kwargs = {
        "host": settings.api_host,
        "port": settings.api_port,
        "proxy_headers": bool(settings.trusted_proxies),
        "log_config": None,
    }
    if settings.ssl_certfile and settings.ssl_keyfile:
        kwargs["ssl_certfile"] = settings.ssl_certfile
        kwargs["ssl_keyfile"] = settings.ssl_keyfile
    if settings.trusted_proxies:
        kwargs["forwarded_allow_ips"] = ",".join(settings.trusted_proxies)
    uvicorn.run(app, **kwargs)


if __name__ == "__main__":
    main()
