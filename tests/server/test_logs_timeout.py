from __future__ import annotations

from contextlib import nullcontext

from gway_wire.surface.server import logs


def _patch_expose(monkeypatch):
    captured = {}
    monkeypatch.setattr(logs, "require_protocol", lambda protocol: None)
    monkeypatch.setattr(logs, "_one_fqdn", lambda *args, **kwargs: "logs.example.com")
    monkeypatch.setattr(
        logs,
        "_values",
        lambda env_file: {
            "GWAY_BASE_DOMAIN": "example.com",
            "GWAY_CERTBOT_EMAIL": "ops@example.com",
        },
    )
    monkeypatch.setattr(logs, "_selected_provider", lambda *args, **kwargs: "godaddy")
    monkeypatch.setattr(logs, "_public_address", lambda *args, **kwargs: "203.0.113.10")
    monkeypatch.setattr(logs, "_web_environment", lambda values: nullcontext())

    def fake_ensure(**kwargs):
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr(logs, "exposure_ensure", fake_ensure)
    return captured


def test_expose_uses_general_timeout_for_dns_wait(monkeypatch) -> None:
    captured = _patch_expose(monkeypatch)

    result = logs.expose(fqdn="logs.example.com", timeout=42)

    assert result == {"success": True}
    assert captured["dns_wait_timeout"] == 42


def test_expose_specific_dns_timeout_overrides_general_timeout(monkeypatch) -> None:
    captured = _patch_expose(monkeypatch)

    logs.expose(
        fqdn="logs.example.com",
        timeout=42,
        dns_wait_timeout=7,
    )

    assert captured["dns_wait_timeout"] == 7


def test_expose_default_timeout_is_five_minutes(monkeypatch) -> None:
    captured = _patch_expose(monkeypatch)

    logs.expose(fqdn="logs.example.com")

    assert captured["dns_wait_timeout"] == 300.0


def test_expose_defaults_to_full_rollback(monkeypatch) -> None:
    captured = _patch_expose(monkeypatch)

    logs.expose(fqdn="logs.example.com")

    assert captured["rollback"] is True
    assert captured["dns_rollback"] is True


def test_expose_can_disable_only_dns_rollback(monkeypatch) -> None:
    captured = _patch_expose(monkeypatch)

    logs.expose(fqdn="logs.example.com", dns_rollback=False)

    assert captured["rollback"] is True
    assert captured["dns_rollback"] is False


def test_expose_passes_global_no_rollback(monkeypatch) -> None:
    captured = _patch_expose(monkeypatch)

    logs.expose(fqdn="logs.example.com", rollback=False)

    assert captured["rollback"] is False
    assert captured["dns_rollback"] is True
