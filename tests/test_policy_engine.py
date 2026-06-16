import unittest
from datetime import datetime, timedelta, timezone

from email_core import NormalizedEmail, evaluate_policy, parse_policy


NOW = datetime.now(timezone.utc).replace(microsecond=0)


def policy(thresholds=None, mode=None, destructive_confidence_threshold=None):
    data = {
        "name": "phase-1b-test-policy",
        "version": "1.0",
        "retention_thresholds": thresholds or {},
        "rules": [
            {
                "name": "loaded-policy-rule",
                "criteria": {"all": [{"field": "labels", "contains": "INBOX"}]},
                "actions": [{"type": "label", "params": {"label": "Matched"}}],
            }
        ],
    }
    if mode is not None:
        data["mode"] = mode
    if destructive_confidence_threshold is not None:
        data["destructive_confidence_threshold"] = destructive_confidence_threshold
    return parse_policy(data)


def email(**overrides):
    data = {
        "id": "message-1",
        "provider": "sample",
        "subject": "Hello",
        "sender": {"address": "sender@example.com", "name": "Sender"},
        "recipients": [{"address": "shola@example.com", "name": "Shola"}],
        "received_at": (NOW - timedelta(days=1)).isoformat(),
        "snippet": "",
        "body_text": "",
        "labels": [],
        "categories": [],
        "headers": {},
        "is_read": False,
    }
    data.update(overrides)
    return NormalizedEmail.from_mapping(data)


class PolicyEngineTests(unittest.TestCase):
    def assert_review_unknown(self, decision):
        self.assertEqual(decision.disposition, "review")
        self.assertEqual(decision.reason_code, "unknown")
        self.assertEqual(decision.confidence, 0.0)
        self.assertFalse(decision.executed)

    def test_valid_non_destructive_classifier_output_is_accepted(self):
        decision = evaluate_policy(
            email(subject="Please remind me"),
            policy(),
            classifier_result={
                "disposition": "remind",
                "reason_code": "calendar_or_meeting",
                "confidence": 0.83,
            },
        )

        self.assertEqual(decision.disposition, "remind")
        self.assertEqual(decision.reason_code, "calendar_or_meeting")
        self.assertEqual(decision.confidence, 0.83)
        self.assertEqual(decision.policy_action["source"], "classifier")
        self.assertFalse(decision.executed)

    def test_unknown_classifier_disposition_defaults_to_review(self):
        decision = evaluate_policy(
            email(),
            policy(),
            {"disposition": "explode", "reason_code": "unknown", "confidence": 0.9},
        )

        self.assert_review_unknown(decision)
        self.assertEqual(decision.policy_action["status"], "invalid_classifier")

    def test_malformed_classifier_output_defaults_to_review(self):
        decision = evaluate_policy(email(), policy(), ["not", "a", "dict"])

        self.assert_review_unknown(decision)
        self.assertEqual(decision.policy_action["status"], "invalid_classifier")

    def test_missing_confidence_defaults_to_review(self):
        decision = evaluate_policy(
            email(),
            policy(),
            {"disposition": "keep", "reason_code": "unknown"},
        )

        self.assert_review_unknown(decision)
        self.assertEqual(decision.policy_action["status"], "missing_confidence")

    def test_low_confidence_destructive_classifier_uses_default_threshold(self):
        decision = evaluate_policy(
            email(
                subject="Monthly newsletter",
                received_at=(NOW - timedelta(days=45)).isoformat(),
                headers={"List-Id": "news.example.com"},
            ),
            policy(),
            {"disposition": "trash", "reason_code": "generic_newsletter", "confidence": 0.79},
        )

        self.assert_review_unknown(decision)
        self.assertEqual(decision.policy_action["status"], "low_confidence")

    def test_stricter_policy_destructive_confidence_threshold_is_used(self):
        decision = evaluate_policy(
            email(
                subject="Monthly newsletter",
                received_at=(NOW - timedelta(days=45)).isoformat(),
                headers={"List-Id": "news.example.com"},
            ),
            policy(destructive_confidence_threshold=0.9),
            {"disposition": "trash", "reason_code": "generic_newsletter", "confidence": 0.85},
        )

        self.assert_review_unknown(decision)
        self.assertEqual(decision.policy_action["status"], "low_confidence")

    def test_lower_policy_destructive_confidence_threshold_does_not_weaken_default(self):
        decision = evaluate_policy(
            email(
                subject="Monthly newsletter",
                received_at=(NOW - timedelta(days=45)).isoformat(),
                headers={"List-Id": "news.example.com"},
            ),
            policy(destructive_confidence_threshold=0.5),
            {"disposition": "trash", "reason_code": "generic_newsletter", "confidence": 0.79},
        )

        self.assert_review_unknown(decision)
        self.assertEqual(decision.policy_action["status"], "low_confidence")

    def test_classifier_alone_cannot_create_destructive_final_disposition(self):
        decision = evaluate_policy(
            email(subject="Hello from a person"),
            policy(),
            {"disposition": "archive", "reason_code": "rejection_notice", "confidence": 0.95},
        )

        self.assert_review_unknown(decision)
        self.assertEqual(decision.policy_action["status"], "requires_deterministic_support")

    def test_classifier_suppress_always_defaults_to_review_in_phase_1b(self):
        decision = evaluate_policy(
            email(subject="Newsletter", received_at=(NOW - timedelta(days=45)).isoformat()),
            policy(),
            {"disposition": "suppress", "reason_code": "generic_newsletter", "confidence": 0.99},
        )

        self.assert_review_unknown(decision)
        self.assertEqual(decision.policy_action["status"], "suppression_out_of_scope")

    def test_newsletter_older_than_policy_threshold_can_be_candidate_trash(self):
        decision = evaluate_policy(
            email(
                subject="Monthly newsletter",
                sender={"address": "news@example.com"},
                received_at=(NOW - timedelta(days=16)).isoformat(),
                headers={"List-Id": "news.example.com"},
            ),
            policy({"newsletter_days": 14}),
        )

        self.assertEqual(decision.disposition, "trash")
        self.assertEqual(decision.reason_code, "generic_newsletter")
        self.assertEqual(decision.policy_action["threshold_days"], 14)
        self.assertFalse(decision.executed)

    def test_newsletter_in_inbox_needs_retention_threshold_for_candidate_trash(self):
        young = evaluate_policy(
            email(
                subject="Weekly newsletter",
                received_at=(NOW - timedelta(days=10)).isoformat(),
                labels=["INBOX"],
                headers={"List-Id": "weekly.example.com"},
            ),
            policy(),
        )
        old = evaluate_policy(
            email(
                subject="Weekly newsletter",
                received_at=(NOW - timedelta(days=45)).isoformat(),
                labels=["INBOX"],
                headers={"List-Id": "weekly.example.com"},
            ),
            policy(),
        )

        self.assertEqual(young.disposition, "review")
        self.assertEqual(old.disposition, "trash")
        self.assertEqual(old.reason_code, "generic_newsletter")
        self.assertIn("loaded-policy-rule", old.matched_rules)
        self.assertFalse(old.executed)

    def test_promotion_older_than_policy_threshold_can_be_candidate_trash(self):
        decision = evaluate_policy(
            email(
                subject="Limited time offer",
                received_at=(NOW - timedelta(days=11)).isoformat(),
                labels=["CATEGORY_PROMOTIONS"],
            ),
            policy({"promotion_days": 10}),
        )

        self.assertEqual(decision.disposition, "trash")
        self.assertEqual(decision.reason_code, "generic_promotion")
        self.assertEqual(decision.policy_action["threshold_days"], 10)
        self.assertFalse(decision.executed)

    def test_promotion_uses_safe_default_when_policy_omits_threshold(self):
        young = evaluate_policy(
            email(
                subject="Limited time offer",
                received_at=(NOW - timedelta(days=29)).isoformat(),
                labels=["CATEGORY_PROMOTIONS"],
            ),
            policy(),
        )
        old = evaluate_policy(
            email(
                subject="Limited time offer",
                received_at=(NOW - timedelta(days=31)).isoformat(),
                labels=["CATEGORY_PROMOTIONS"],
            ),
            policy(),
        )

        self.assertEqual(young.disposition, "review")
        self.assertEqual(old.disposition, "trash")
        self.assertEqual(old.reason_code, "generic_promotion")
        self.assertEqual(old.policy_action["threshold_days"], 30)
        self.assertFalse(old.executed)

    def test_job_alert_older_than_policy_threshold_can_be_candidate_trash(self):
        decision = evaluate_policy(
            email(
                subject="Job alert: Python developer",
                sender={"address": "alerts@linkedin.com"},
                received_at=(NOW - timedelta(days=8)).isoformat(),
            ),
            policy({"job_alert_days": 6}),
        )

        self.assertEqual(decision.disposition, "trash")
        self.assertEqual(decision.reason_code, "job_alert")
        self.assertEqual(decision.policy_action["threshold_days"], 6)
        self.assertFalse(decision.executed)

    def test_rejection_email_becomes_candidate_archive_not_trash(self):
        decision = evaluate_policy(
            email(
                subject="Application update",
                body_text="We regret to inform you that we are not moving forward.",
                received_at=(NOW - timedelta(days=1)).isoformat(),
            ),
            policy(),
        )

        self.assertEqual(decision.disposition, "archive")
        self.assertEqual(decision.reason_code, "rejection_notice")
        self.assertFalse(decision.protected)
        self.assertFalse(decision.executed)

    def test_application_update_in_promotions_is_protected_reviewed(self):
        decision = evaluate_policy(
            email(
                subject="Application status update",
                body_text="Please complete the next step in your application.",
                labels=["CATEGORY_PROMOTIONS"],
                received_at=(NOW - timedelta(days=60)).isoformat(),
            ),
            policy(),
        )

        self.assertEqual(decision.disposition, "review")
        self.assertEqual(decision.reason_code, "application_update")
        self.assertTrue(decision.protected)
        self.assertFalse(decision.executed)

    def test_direct_personal_request_is_protected(self):
        decision = evaluate_policy(
            email(
                subject="Can you review this?",
                sender={"address": "person@example.com", "name": "Person"},
                body_text="Hi Shola, could you please review this today?",
            ),
            policy(),
        )

        self.assertEqual(decision.disposition, "review")
        self.assertEqual(decision.reason_code, "direct_personal_request")
        self.assertTrue(decision.protected)
        self.assertFalse(decision.executed)

    def test_security_account_payment_message_is_protected(self):
        for subject, reason in (
            ("Security alert for your account", "security_or_account"),
            ("Payment failed for invoice 123", "payment_or_invoice"),
        ):
            with self.subTest(subject=subject):
                decision = evaluate_policy(
                    email(subject=subject, received_at=(NOW - timedelta(days=45)).isoformat()),
                    policy(),
                )

                self.assertEqual(decision.disposition, "review")
                self.assertEqual(decision.reason_code, reason)
                self.assertTrue(decision.protected)
                self.assertFalse(decision.executed)

    def test_mode_comes_from_policy_but_executed_is_always_false(self):
        decision = evaluate_policy(
            email(
                subject="Weekly newsletter",
                received_at=(NOW - timedelta(days=45)).isoformat(),
                headers={"List-Id": "weekly.example.com"},
            ),
            policy(mode="live"),
        )

        self.assertEqual(decision.mode, "live")
        self.assertFalse(decision.executed)

    def test_mode_defaults_to_dry_run_and_matched_rules_is_tuple(self):
        decision = evaluate_policy(
            email(labels=["INBOX"]),
            policy(),
        )

        self.assertEqual(decision.mode, "dry_run")
        self.assertIsInstance(decision.matched_rules, tuple)


if __name__ == "__main__":
    unittest.main()
