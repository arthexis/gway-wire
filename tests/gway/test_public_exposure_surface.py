from __future__ import annotations

import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from gway_wire.surface.server import logs, public


class PublicExposureSurfaceTests(unittest.TestCase):
    def test_logs_exposure_delegates_to_generic_public_surface(self) -> None:
        calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

        def fake_expose(*name, **kwargs):
            calls.append((name, kwargs))
            return {"success": True}

        with patch.object(logs, "public_expose", fake_expose):
            result = logs.expose("logs.example.test")

        self.assertEqual(result, {"success": True})
        self.assertEqual(calls[0][0], ("logs.example.test",))
        self.assertEqual(calls[0][1]["upstream"], "http://127.0.0.1:8040")
        self.assertEqual(calls[0][1]["health_path"], "/health")

    def test_generic_public_exposure_reuses_gway_web(self) -> None:
        calls: list[dict[str, object]] = []
        values = {
            "GWAY_DNS_PROVIDER": "godaddy",
            "GWAY_BASE_DOMAIN": "example.test",
            "GWAY_PUBLIC_GATEWAY_IP": "203.0.113.10",
            "GWAY_CERTBOT_EMAIL": "ops@example.test",
        }

        def fake_ensure(**kwargs):
            calls.append(kwargs)
            return {"success": True, "fqdn": kwargs["fqdn"]}

        with tempfile.TemporaryDirectory() as temporary:
            env_file = Path(temporary) / "server.env"
            with (
                patch.object(public, "_values", return_value=values),
                patch.object(public, "_web_environment", return_value=nullcontext()),
                patch.object(public, "exposure_ensure", fake_ensure),
            ):
                result = public.expose(
                    "repo.example.test",
                    upstream="http://127.0.0.1:8050",
                    env_file=env_file,
                )

        self.assertIs(result["success"], True)
        self.assertEqual(
            calls,
            [
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
            ],
        )


if __name__ == "__main__":
    unittest.main()
