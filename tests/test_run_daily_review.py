import contextlib
import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
EMAILS_FIXTURE = FIXTURES_DIR / "sample_emails.json"
POLICY_FIXTURE = FIXTURES_DIR / "sample_policy.json"


class RunDailyReviewTests(unittest.TestCase):
    def test_run_function_reads_fixtures_and_produces_decisions(self):
        from email_core.run_daily_review import run_dry_review

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            report_path = tmp / "reports" / "daily-review.md"
            audit_path = tmp / "runs" / "audit-log.jsonl"

            summary = run_dry_review(EMAILS_FIXTURE, POLICY_FIXTURE, report_path, audit_path)

            self.assertEqual(summary.emails_processed, 2)
            self.assertEqual(summary.decisions_produced, 2)
            self.assertEqual(summary.report_path, report_path)
            self.assertEqual(summary.audit_path, audit_path)

    def test_run_function_writes_report_and_audit_and_creates_directories(self):
        from email_core.run_daily_review import run_dry_review

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            report_path = tmp / "nested" / "reports" / "daily-review.md"
            audit_path = tmp / "nested" / "runs" / "audit-log.jsonl"

            run_dry_review(EMAILS_FIXTURE, POLICY_FIXTURE, report_path, audit_path)

            self.assertTrue(report_path.exists())
            self.assertTrue(audit_path.exists())
            self.assertIn("# Daily Mail Review", report_path.read_text(encoding="utf-8"))
            self.assertIn("Dry run report", report_path.read_text(encoding="utf-8"))

    def test_audit_jsonl_has_one_line_per_decision_and_is_parseable(self):
        from email_core.run_daily_review import run_dry_review

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            audit_path = tmp / "runs" / "audit-log.jsonl"

            summary = run_dry_review(
                EMAILS_FIXTURE,
                POLICY_FIXTURE,
                tmp / "reports" / "daily-review.md",
                audit_path,
            )

            lines = audit_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), summary.decisions_produced)
            parsed = [json.loads(line) for line in lines]
            self.assertTrue(all(record["executed"] is False for record in parsed))

    def test_main_rejects_live_mode_in_phase_1d(self):
        from email_core.run_daily_review import main

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--emails",
                    str(EMAILS_FIXTURE),
                    "--policy",
                    str(POLICY_FIXTURE),
                    "--live",
                ]
            )

        self.assertNotEqual(exit_code, 0)
        self.assertIn("live mode is not available", stderr.getvalue().lower())

    def test_main_returns_non_zero_for_missing_email_fixture(self):
        from email_core.run_daily_review import main

        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir, contextlib.redirect_stderr(stderr):
            tmp = Path(tmpdir)
            exit_code = main(
                [
                    "--emails",
                    str(tmp / "missing-emails.json"),
                    "--policy",
                    str(POLICY_FIXTURE),
                    "--report",
                    str(tmp / "reports" / "daily-review.md"),
                    "--audit",
                    str(tmp / "runs" / "audit-log.jsonl"),
                ]
            )

        self.assertNotEqual(exit_code, 0)
        self.assertIn("missing-emails.json", stderr.getvalue())

    def test_main_returns_non_zero_for_missing_policy_fixture(self):
        from email_core.run_daily_review import main

        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir, contextlib.redirect_stderr(stderr):
            tmp = Path(tmpdir)
            exit_code = main(
                [
                    "--emails",
                    str(EMAILS_FIXTURE),
                    "--policy",
                    str(tmp / "missing-policy.json"),
                    "--report",
                    str(tmp / "reports" / "daily-review.md"),
                    "--audit",
                    str(tmp / "runs" / "audit-log.jsonl"),
                ]
            )

        self.assertNotEqual(exit_code, 0)
        self.assertIn("missing-policy.json", stderr.getvalue())

    def test_cli_module_does_not_import_provider_modules(self):
        importlib.import_module("email_core.run_daily_review")

        self.assertNotIn("gmail_handler", sys.modules)
        self.assertNotIn("outlook_handler", sys.modules)


if __name__ == "__main__":
    unittest.main()
