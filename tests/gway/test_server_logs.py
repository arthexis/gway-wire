from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gway_wire.surface.server import logs


class ServerLogsTests(unittest.TestCase):
    def test_log_exposure_reuses_wire_dns_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env_file = Path(temporary) / "server.env"
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

            with patch.object(logs, "exposure_ensure", fake_ensure):
                result = logs.expose(
                    fqdn="logs.register.arthexis.com",
                    env_file=env_file,
                )

        self.assertIs(result["success"], True)
        self.assertEqual(captured["fqdn"], "logs.register.arthexis.com")
        self.assertEqual(captured["upstream"], "http://127.0.0.1:8040")
        self.assertEqual(captured["dns_provider"], "godaddy")
        self.assertEqual(captured["dns_zone"], "arthexis.com")
        self.assertEqual(captured["public_address"], "203.0.113.10")
        self.assertEqual(captured["email"], "ops@example.com")


if __name__ == "__main__":
    unittest.main()
