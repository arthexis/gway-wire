from __future__ import annotations

import unittest
from contextlib import nullcontext
from unittest.mock import patch

from gway_wire.surface.server import logs, public


class PublicCheckSurfaceTests(unittest.TestCase):
    def test_public_check_forwards_resolved_arguments(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_check(**kwargs):
            calls.append(kwargs)
            return {"ok": True}

        with (
            patch.object(public, "_values", return_value={"GWAY_BASE_DOMAIN": "example.test"}),
            patch.object(public, "_one_fqdn", return_value="repo.example.test"),
            patch.object(public, "_selected_provider", return_value="provider"),
            patch.object(public, "_public_address", return_value="address"),
            patch.object(public, "_web_environment", return_value=nullcontext()),
            patch.object(public, "exposure_check", fake_check),
        ):
            result = public.check("repo.example.test", timeout=11.0)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            calls,
            [
                {
                    "fqdn": "repo.example.test",
                    "dns_provider": "provider",
                    "dns_zone": "example.test",
                    "public_address": "address",
                    "timeout": 11.0,
                }
            ],
        )

    def test_logs_check_delegates_to_public_check(self) -> None:
        calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

        def fake_check(*name, **kwargs):
            calls.append((name, kwargs))
            return {"ok": True}

        with patch.object(logs, "public_check", fake_check):
            result = logs.check("logs.example.test", timeout=9.0)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls[0][0], ("logs.example.test",))
        self.assertEqual(calls[0][1]["timeout"], 9.0)


if __name__ == "__main__":
    unittest.main()
