"""Public exposure helpers for the authenticated GWAY log service."""

from __future__ import annotations

from pathlib import Path

from gway_wire.gway.protocols import DEFAULT_PROTOCOL
from gway_wire.surface.server import _DEFAULT_ENV_FILE
from gway_wire.surface.server.public import check as public_check
from gway_wire.surface.server.public import expose as public_expose

_DEFAULT_UPSTREAM = "http://127.0.0.1:8040"
_DEFAULT_EXPOSURE_TIMEOUT = 300.0


def expose(
    *name: str,
    fqdn: str | None = None,
    domain: str | None = None,
    upstream: str = _DEFAULT_UPSTREAM,
    health_path: str = "/health",
    dns_provider: str | None = None,
    provider: str | None = None,
    public_address: str | None = None,
    cert_email: str | None = None,
    timeout: float = _DEFAULT_EXPOSURE_TIMEOUT,
    dns_wait_timeout: float | None = None,
    rollback: bool = True,
    dns_rollback: bool = True,
    env_file: Path = _DEFAULT_ENV_FILE,
    protocol: str = DEFAULT_PROTOCOL,
) -> dict[str, object]:
    """Expose the loopback log service through the generic public Web path."""
    return public_expose(
        *name,
        fqdn=fqdn,
        domain=domain,
        upstream=upstream,
        health_path=health_path,
        dns_provider=dns_provider,
        provider=provider,
        public_address=public_address,
        cert_email=cert_email,
        timeout=timeout,
        dns_wait_timeout=dns_wait_timeout,
        rollback=rollback,
        dns_rollback=dns_rollback,
        env_file=env_file,
        protocol=protocol,
    )


def check(
    *name: str,
    fqdn: str | None = None,
    domain: str | None = None,
    dns_provider: str | None = None,
    provider: str | None = None,
    public_address: str | None = None,
    env_file: Path = _DEFAULT_ENV_FILE,
    timeout: float = 5.0,
    protocol: str = DEFAULT_PROTOCOL,
) -> dict[str, object]:
    """Check the log-service FQDN through the generic public Web path."""
    return public_check(
        *name,
        fqdn=fqdn,
        domain=domain,
        dns_provider=dns_provider,
        provider=provider,
        public_address=public_address,
        env_file=env_file,
        timeout=timeout,
        protocol=protocol,
    )
