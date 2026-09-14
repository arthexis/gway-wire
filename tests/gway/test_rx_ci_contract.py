from __future__ import annotations

import shlex
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "recipes" / "ubuntu22-live.rx"
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

        self.assertEqual(statements[0], "upgrade gway --force")
        self.assertEqual(statements[1], "reload")
        self.assertIn("upgrade wire", statements)
        self.assertIn("upgrade web", statements)
        self.assertNotIn("upgrade wire --force", statements)
        self.assertNotIn("upgrade web --force", statements)
        self.assertIn("web site", statements)
        self.assertEqual(
            statements[-1],
            "wire server deploy --fqdn [fqdn] --cert-email [cert_email]",
        )

    def test_live_workflow_executes_checked_in_recipe_directly(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("default: recipes/ubuntu22-live.rx", text)
        self.assertIn("validate-recipe-path.sh", text)
        self.assertIn('gway --json recipe', text)
        self.assertIn("--fqdn register.arthexis.com", text)
        self.assertIn("--cert-email tecnologia@gelectriic.com", text)

        # Lifecycle policy belongs to the .rx file, not duplicated as YAML shell steps.
        self.assertNotIn("gway upgrade wire --force", text)
        self.assertNotIn("gway install web", text)
        self.assertNotIn("gway upgrade web --force", text)

    def test_live_workflow_parses_top_level_recipe_and_readiness_results(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("json.load(sys.stdin)", text)
        self.assertIn('data.get("success") is True', text)
        self.assertIn('data.get("ok") is True', text)
        self.assertIn('data.get("ready") is True', text)
        self.assertNotIn("grep -Eq", text)
        self.assertIn("gway --json wire server check", text)

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
