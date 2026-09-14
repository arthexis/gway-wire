from __future__ import annotations

from pathlib import Path

from gway_wire.surface.server import logs


def test_log_exposure_reuses_wire_dns_configuration(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "server.env"
    env_file.write_text(
        "\n".join(
            [
                "GWAY_DNS_PROVIDER=godaddy",
                "GWAY_BASE_DOMAIN=arthexis.com",
                "GWAY_PUBLIC_GATEWAY_IP=203.0.113.10",
                "GWAY_CERTBOT_EMAIL=ops@example.com",
                "GWAY_GODADDY_KEY=test-key",
                "GWAY_GODADDY_SECRET=test-secret",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_ensure(**kwargs):
        captured.update(kwargs)
        return {"success": True, "fqdn": kwargs["fqdn"]}

    monkeypatch.setattr(logs, "exposure_ensure", fake_ensure)

    result = logs.expose(fqdn="logs.register.arthexis.com", env_file=env_file)

    assert result["success"] is True
    assert captured["fqdn"] == "logs.register.arthexis.com"
    assert captured["upstream"] == "http://127.0.0.1:8040"
    assert captured["dns_provider"] == "godaddy"
    assert captured["dns_zone"] == "arthexis.com"
    assert captured["public_address"] == "203.0.113.10"
    assert captured["email"] == "ops@example.com"
