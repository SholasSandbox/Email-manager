import subprocess
import sys
import tomllib
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class PackagingReadinessTests(unittest.TestCase):
    def test_pyproject_declares_safe_console_entrypoint(self):
        pyproject_path = ROOT_DIR / "pyproject.toml"

        self.assertTrue(pyproject_path.exists(), "pyproject.toml should exist for packaging readiness")
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

        project = pyproject["project"]
        self.assertEqual(project["scripts"]["email-review-dry-run"], "email_core.run_daily_review:main")
        self.assertIn("gmail", project["optional-dependencies"])
        self.assertNotIn("outlook", project["optional-dependencies"])

    def test_python_m_email_core_exposes_dry_run_cli_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "email_core", "--help"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--provider", result.stdout)
        self.assertIn("Gmail metadata", result.stdout)

    def test_gitignore_covers_local_packaging_artifacts(self):
        gitignore = (ROOT_DIR / ".gitignore").read_text(encoding="utf-8")

        self.assertIn(".venv/", gitignore)
        self.assertIn("build/", gitignore)
        self.assertIn("dist/", gitignore)
        self.assertIn("*.egg-info/", gitignore)


if __name__ == "__main__":
    unittest.main()
