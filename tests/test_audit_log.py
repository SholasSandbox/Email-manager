import json
import unittest

from email_core import (
    NormalizedEmail,
    PolicyDecision,
    decision_to_audit_record,
    render_audit_jsonl,
)


def decision(**overrides):
    data = {
        "message_id": "message-1",
        "provider": "gmail",
        "disposition": "trash",
        "reason_code": "generic_newsletter",
        "confidence": 0.93,
        "policy_action": {"status": "candidate_trash_after_retention_threshold"},
        "mode": "dry_run",
        "executed": False,
        "protected": False,
        "matched_rules": ("newsletter_retention",),
    }
    data.update(overrides)
    return PolicyDecision(**data)


def email(body_text="do not log this body"):
    return NormalizedEmail.from_mapping(
        {
            "id": "message-1",
            "provider": "gmail",
            "subject": "Safe subject",
            "sender": {"address": "updates@example.com", "name": "Updates"},
            "recipients": [{"address": "shola@example.com", "name": "Shola"}],
            "received_at": "2026-06-16T09:00:00Z",
            "snippet": "safe snippet",
            "body_text": body_text,
            "body_html": "<p>do not log this html</p>",
        }
    )


class AuditLogTests(unittest.TestCase):
    def test_decision_to_audit_record_includes_required_fields(self):
        record = decision_to_audit_record(
            decision(),
            email=email(),
            timestamp="2026-06-04T05:45:00Z",
        )

        self.assertEqual(record["timestamp"], "2026-06-04T05:45:00Z")
        self.assertEqual(record["provider"], "gmail")
        self.assertEqual(record["message_id"], "message-1")
        self.assertEqual(record["from_domain"], "example.com")
        self.assertEqual(record["subject"], "Safe subject")
        self.assertEqual(record["disposition"], "trash")
        self.assertEqual(record["reason_code"], "generic_newsletter")
        self.assertEqual(record["confidence"], 0.93)
        self.assertEqual(record["policy_action"], {"status": "candidate_trash_after_retention_threshold"})
        self.assertEqual(record["mode"], "dry_run")
        self.assertFalse(record["executed"])
        self.assertFalse(record["protected"])
        self.assertEqual(record["matched_rules"], ["newsletter_retention"])

    def test_matched_rules_tuple_becomes_json_safe_list(self):
        record = decision_to_audit_record(decision(matched_rules=("a", "b")), timestamp="2026-06-04T05:45:00Z")

        self.assertEqual(record["matched_rules"], ["a", "b"])

    def test_render_audit_jsonl_returns_one_json_object_per_line(self):
        records = [
            decision_to_audit_record(decision(message_id="a"), timestamp="2026-06-04T05:45:00Z"),
            decision_to_audit_record(decision(message_id="b"), timestamp="2026-06-04T05:46:00Z"),
        ]

        output = render_audit_jsonl(records)
        lines = output.splitlines()

        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["message_id"], "a")
        self.assertEqual(json.loads(lines[1])["message_id"], "b")

    def test_audit_log_does_not_include_full_email_body_fields(self):
        record = decision_to_audit_record(
            decision(),
            email=email(body_text="VERY SECRET BODY"),
            timestamp="2026-06-04T05:45:00Z",
        )
        output = render_audit_jsonl([record])

        self.assertNotIn("body_text", record)
        self.assertNotIn("body_html", record)
        self.assertNotIn("VERY SECRET BODY", output)
        self.assertNotIn("do not log this html", output)


if __name__ == "__main__":
    unittest.main()
