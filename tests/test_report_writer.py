import unittest

from email_core import NormalizedEmail, PolicyDecision, render_daily_review


def decision(message_id, disposition, reason_code="unknown", **overrides):
    data = {
        "message_id": message_id,
        "provider": "sample",
        "disposition": disposition,
        "reason_code": reason_code,
        "confidence": 0.91,
        "policy_action": {"status": f"candidate_{disposition}"},
        "executed": False,
        "mode": "dry_run",
        "protected": False,
        "matched_rules": ("rule-a",),
    }
    data.update(overrides)
    return PolicyDecision(**data)


def email(message_id, subject="Safe subject", body_text="do not include this body"):
    return NormalizedEmail.from_mapping(
        {
            "id": message_id,
            "provider": "sample",
            "subject": subject,
            "sender": {"address": "sender@example.com", "name": "Sender"},
            "recipients": [{"address": "shola@example.com", "name": "Shola"}],
            "received_at": "2026-06-16T09:00:00Z",
            "snippet": "safe snippet",
            "body_text": body_text,
        }
    )


class ReportWriterTests(unittest.TestCase):
    def test_report_includes_all_required_section_headings(self):
        report = render_daily_review([])

        for heading in (
            "# Daily Mail Review",
            "## Remind",
            "## Review",
            "## Keep",
            "## Candidate Archive - Dry Run Only",
            "## Candidate Trash - Dry Run Only",
            "## Suppression Candidates",
            "## Action Summary",
            "## Errors / Warnings",
        ):
            self.assertIn(heading, report)

    def test_decisions_are_grouped_under_disposition_sections(self):
        decisions = [
            decision("remind-1", "remind", "calendar_or_meeting"),
            decision("review-1", "review", "direct_personal_request", protected=True),
            decision("keep-1", "keep", "unknown"),
            decision("archive-1", "archive", "rejection_notice"),
            decision("trash-1", "trash", "generic_newsletter"),
            decision("suppress-1", "suppress", "automated_notification"),
        ]

        report = render_daily_review(decisions)

        self.assert_section_contains(report, "## Remind", "## Review", "remind-1")
        self.assert_section_contains(report, "## Review", "## Keep", "review-1")
        self.assert_section_contains(report, "## Keep", "## Candidate Archive", "keep-1")
        self.assert_section_contains(report, "## Candidate Archive", "## Candidate Trash", "archive-1")
        self.assert_section_contains(report, "## Candidate Trash", "## Suppression", "trash-1")
        self.assert_section_contains(report, "## Suppression", "## Action Summary", "suppress-1")

    def test_report_clearly_states_dry_run_and_no_executed_actions(self):
        report = render_daily_review([decision("trash-1", "trash", "generic_newsletter")])

        self.assertIn("Dry run", report)
        self.assertIn("No mailbox actions were executed", report)
        self.assertIn("Candidate Trash - Dry Run Only", report)

    def test_report_renders_without_email_metadata(self):
        report = render_daily_review([decision("review-1", "review")])

        self.assertIn("review-1", report)
        self.assertIn("provider=sample", report)

    def test_report_includes_safe_metadata_but_not_full_body(self):
        report = render_daily_review(
            [decision("review-1", "review", "direct_personal_request")],
            emails_by_id={"review-1": email("review-1", body_text="VERY SECRET BODY")},
        )

        self.assertIn("sender@example.com", report)
        self.assertIn("Safe subject", report)
        self.assertNotIn("VERY SECRET BODY", report)

    def test_report_includes_action_summary_counts(self):
        report = render_daily_review(
            [
                decision("remind-1", "remind"),
                decision("review-1", "review"),
                decision("trash-1", "trash"),
                decision("trash-2", "trash"),
            ]
        )

        self.assertIn("- remind: 1", report)
        self.assertIn("- review: 1", report)
        self.assertIn("- trash: 2", report)

    def assert_section_contains(self, report, start_heading, end_heading, expected):
        start = report.index(start_heading)
        end = report.index(end_heading, start + len(start_heading))
        self.assertIn(expected, report[start:end])


if __name__ == "__main__":
    unittest.main()
