from __future__ import annotations

import shlex
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "recipes" / "ubuntu22-live.rx"
ARTHEXIS_BOOTSTRAP_RECIPE = ROOT / "recipes" / "arthexis-bootstrap.rx"
WORKFLOW = ROOT / ".github" / "workflows" / "ubuntu22-live.yml"
VALIDATOR = ROOT / ".github" / "scripts" / "validate-recipe-path.sh"


class RxCiContractTests(unittest.TestCase):
    def test_default_live_recipe_is_tokenizable_and_exercises_reload(self) -> None:
        self.assertTrue(RECIPE.is_file())
        statements = [
            line.strip()
            for line in RECIPE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        for statement in statements:
            self.assertTrue(shlex.split(statement))

        self.assertEqual(
            statements[0],
            "log --tags ci,ubuntu22 --to [log_destination] --consumers wire,arthexis",
        )
        self.assertEqual(statements[1], "upgrade gway --force")
        self.assertEqual(statements[2], "reload")
        self.assertIn("upgrade wire --install", statements)
        self.assertIn("upgrade web --install", statements)
        self.assertNotIn("upgrade wire --force", statements)
        self.assertNotIn("upgrade web --force", statements)
        self.assertIn("web site", statements)
        self.assertEqual(
            statements[-1],
            "wire server deploy --fqdn [fqdn] --cert-email [cert_email]",
        )

    def test_arthexis_bootstrap_recipe_is_persistent_and_health_checked(self) -> None:
        self.assertTrue(ARTHEXIS_BOOTSTRAP_RECIPE.is_file())
        statements = [
            line.strip()
            for line in ARTHEXIS_BOOTSTRAP_RECIPE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        for statement in statements:
            self.assertTrue(shlex.split(statement))

        self.assertEqual(
            statements,
            [
                "log --tags watchtower,ubuntu22 --to [log_destination] --consumer arthexis",
                "upgrade arthexis --install --service --service-profile Watchtower --role Watchtower",
                "arthexis status --json",
                "arthexis good",
            ],
        )
        self.assertFalse(any("uninstall" in statement for statement in statements))

    def test_live_workflow_executes_checked_in_recipe_directly(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("default: recipes/ubuntu22-live.rx", text)
        self.assertIn("validate-recipe-path.sh", text)
        self.assertIn("gway --json recipe", text)
        self.assertIn("--fqdn register.arthexis.com", text)
        self.assertIn("--cert-email tecnologia@gelectriic.com", text)
        self.assertIn('--log_destination "${GWAY_LOG_DESTINATION}"', text)

        # Bootstrap establishes required managed projects without destructive
        # force-upgrade behavior; normal lifecycle policy remains in the .rx file.
        self.assertNotIn("gway upgrade wire --force", text)
        self.assertNotIn("gway upgrade web --force", text)
        self.assertIn("sudo -n gway upgrade web --install", text)
        self.assertIn("sudo -n gway upgrade wire --install", text)
        self.assertIn("sudo -n gway upgrade repo --install", text)

    def test_live_workflow_uses_explicit_log_dns(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("GWAY_LOG_DESTINATION: https://logs.arthexis.com", text)
        self.assertIn("--fqdn logs.arthexis.com", text)
        self.assertIn("--dns-provider godaddy", text)
        self.assertNotIn("logs.register.arthexis.com", text)

    def test_live_workflow_primes_log_consumers_before_recipe(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        log_service = text.index("- name: Bootstrap live GWAY log service")
        consumers = text.index("- name: Prime local log consumers")
        recipe = text.index("- name: Execute trusted RX recipe")
        self.assertLess(log_service, consumers)
        self.assertLess(consumers, recipe)
        self.assertIn("--consumers wire,arthexis", text)
        self.assertIn("GATEWAY_LOG_RUN_ID", text)
        self.assertIn("- name: Verify gateway recipe log publication", text)

    def test_live_workflow_reserves_job_time_for_log_readback(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("- name: Execute trusted RX recipe\n        timeout-minutes: 8", text)
        self.assertIn(
            "- name: Bootstrap persistent Arthexis Watchtower\n        timeout-minutes: 6",
            text,
        )
        self.assertIn("timeout-minutes: 25", text)
        gateway = text.index("- name: Execute trusted RX recipe")
        gateway_readback = text.index("- name: Verify gateway recipe log publication")
        watchtower = text.index("- name: Bootstrap persistent Arthexis Watchtower")
        watchtower_readback = text.index("- name: Verify Watchtower log publication")
        self.assertLess(gateway, gateway_readback)
        self.assertLess(watchtower, watchtower_readback)

    def test_live_workflow_does_not_require_ingest_secret(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("GWAY_LOG_INGEST_TOKEN", text)
        self.assertNotIn('GWAY_LOG_TOKEN="${', text)
        self.assertIn("GWAY_LOG_READ_TOKEN", text)
        self.assertIn("if: env.GWAY_LOG_READ_TOKEN != ''", text)

    def test_main_live_workflow_bootstraps_arthexis_after_gateway_health(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        health = text.index("- name: Verify live public health")
        arthexis = text.index("- name: Bootstrap persistent Arthexis Watchtower")
        self.assertLess(health, arthexis)
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("if: github.event_name == 'push'", text)
        self.assertIn("recipes/arthexis-bootstrap.rx", text)
        self.assertIn("--role Watchtower", text)
        self.assertIn("arthexis bootstrap result=%r", text)

    def test_live_workflow_parses_top_level_recipe_and_readiness_results(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("json.loads(sys.argv[1])", text)
        self.assertNotIn("json.load(sys.stdin)", text)
        self.assertIn('data.get("success") is True', text)
        self.assertIn('data.get("ok") is True', text)
        self.assertIn('data.get("ready") is True', text)
        self.assertNotIn("grep -Eq", text)
        self.assertIn("gway --json wire server check", text)

    def test_live_workflow_verifies_managed_checkout_provenance(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("/var/lib/gway/projects/arthexis/gway-wire", text)
        self.assertIn("/var/lib/gway/projects/arthexis/gway-web", text)
        self.assertIn("ls-remote --exit-code origin refs/heads/main", text)
        self.assertIn('test "${head}" = "${upstream}"', text)
        self.assertIn("status --porcelain", text)
        self.assertIn("managed checkout is dirty", text)

    def test_recipe_path_validator_accepts_tracked_default(self) -> None:
        result = subprocess.run(
            ["bash", str(VALIDATOR), "recipes/ubuntu22-live.rx"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "recipes/ubuntu22-live.rx")

    def test_recipe_path_validator_accepts_tracked_arthexis_bootstrap(self) -> None:
        result = subprocess.run(
            ["bash", str(VALIDATOR), "recipes/arthexis-bootstrap.rx"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "recipes/arthexis-bootstrap.rx")

    def test_recipe_path_validator_rejects_untrusted_paths(self) -> None:
        for candidate in (
            "README.md",
            "../outside.rx",
            "recipes/../README.md",
            "recipes/missing.rx",
        ):
            with self.subTest(candidate=candidate):
                result = subprocess.run(
                    ["bash", str(VALIDATOR), candidate],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
