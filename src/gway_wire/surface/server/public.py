"""Generic public exposure for loopback services managed by the Wire gateway."""

from __future__ import annotations

import os
from pathlib import Path

from gway_web import exposure_check, exposure_ensure

from gway_wire.gway.protocols import DEFAULT_PROTOCOL, require_protocol
from gway_wire.surface.server import (
    _DEFAULT_ENV_FILE,
    _one_fqdn,
    _public_address,
    _selected_provider,
    _values,
    _web_environment,
)

_DEFAULT_EXPOSURE_TIMEOUT = 300.0


def expose(
    *name: str,
    upstream: str,
    fqdn: str | None = None,
    domain: str | None = None,
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
    """Expose one loopback HTTP service at an exact HTTPS FQDN."""
    require_protocol(protocol)
    target = _one_fqdn(name, fqdn=fqdn, domain=domain)
    values = _values(env_file)
    selected_provider = _selected_provider(values, dns_provider, provider)
    address = _public_address(values, public_address)
    email = (
        cert_email
        or values.get("GWAY_CERTBOT_EMAIL")
        or os.environ.get("GWAY_CERTBOT_EMAIL")
    )
    resolved_dns_wait_timeout = timeout if dns_wait_timeout is None else dns_wait_timeout

    with _web_environment(values):
        return exposure_ensure(
            fqdn=target,
            upstream=upstream,
            health_path=health_path,
            certbot=True,
            dns_provider=selected_provider,
            dns_zone=values.get("GWAY_BASE_DOMAIN") or None,
            public_address=address,
            email=email,
            agree_tos=True,
            dns_wait_timeout=resolved_dns_wait_timeout,
            rollback=rollback,
            dns_rollback=dns_rollback,
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
    """Check DNS, TLS, Nginx, and public health for one exposed FQDN."""
    require_protocol(protocol)
    target = _one_fqdn(name, fqdn=fqdn, domain=domain)
    values = _values(env_file)
    selected_provider = _selected_provider(values, dns_provider, provider)
    address = _public_address(values, public_address)
    with _web_environment(values):
        return exposure_check(
            fqdn=target,
            dns_provider=selected_provider,
            dns_zone=values.get("GWAY_BASE_DOMAIN") or None,
            public_address=address,
            timeout=timeout,
        )
