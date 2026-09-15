from __future__ import annotations

from contextlib import nullcontext

from gway_wire.surface.server import logs, public


def test_logs_exposure_delegates_to_generic_public_surface(monkeypatch):
    calls = []

    def fake_expose(*name, **kwargs):
        calls.append((name, kwargs))
        return {"success": True}

    monkeypatch.setattr(logs, "public_expose", fake_expose)

    result = logs.expose("logs.example.test")

    assert result == {"success": True}
    assert calls[0][0] == ("logs.example.test",)
    assert calls[0][1]["upstream"] == "http://127.0.0.1:8040"
    assert calls[0][1]["health_path"] == "/health"


def test_generic_public_exposure_reuses_gway_web(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        public,
        "_values",
        lambda _path: {
            "GWAY_DNS_PROVIDER": "godaddy",
            "GWAY_BASE_DOMAIN": "example.test",
            "GWAY_PUBLIC_GATEWAY_IP": "203.0.113.10",
            "GWAY_CERTBOT_EMAIL": "ops@example.test",
        },
    )
    monkeypatch.setattr(public, "_web_environment", lambda _values: nullcontext())

    def fake_ensure(**kwargs):
        calls.append(kwargs)
        return {"success": True, "fqdn": kwargs["fqdn"]}

    monkeypatch.setattr(public, "exposure_ensure", fake_ensure)

    result = public.expose(
        "repo.example.test",
        upstream="http://127.0.0.1:8050",
        env_file=tmp_path / "server.env",
    )

    assert result["success"] is True
    assert calls == [
        {
            "fqdn": "repo.example.test",
            "upstream": "http://127.0.0.1:8050",
            "health_path": "/health",
            "certbot": True,
            "dns_provider": "godaddy",
            "dns_zone": "example.test",
            "public_address": "203.0.113.10",
            "email": "ops@example.test",
            "agree_tos": True,
            "dns_wait_timeout": 300.0,
            "rollback": True,
            "dns_rollback": True,
        }
    ]
