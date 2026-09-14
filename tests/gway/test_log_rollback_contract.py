from __future__ import annotations

import inspect
from pathlib import Path

from gway_wire.surface.server import logs


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ubuntu22-live.yml"


def test_log_expose_declares_general_and_dns_rollback_flags() -> None:
    signature = inspect.signature(logs.expose)

    assert signature.parameters["rollback"].default is True
    assert signature.parameters["dns_rollback"].default is True


def test_live_log_bootstrap_disables_only_dns_rollback() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    bootstrap = text.split("- name: Bootstrap live GWAY log service", 1)[1].split(
        "- name: Prime local log consumers", 1
    )[0]

    assert "--no-dns-rollback" in bootstrap
    assert "--no-rollback" not in bootstrap
