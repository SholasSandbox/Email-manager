import json
import unittest
from pathlib import Path

from email_core import EmailContact, EmailProvider, NormalizedEmail


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class NormalizedEmailTests(unittest.TestCase):
    def test_from_mapping_normalizes_fixture_email(self):
        sample = json.loads((FIXTURES_DIR / "sample_emails.json").read_text())[0]

        email = NormalizedEmail.from_mapping(sample)

        self.assertEqual(email.id, "sample-gmail-001")
        self.assertEqual(email.provider, EmailProvider.GMAIL)
        self.assertEqual(email.sender, EmailContact("updates@example.com", "Example Updates"))
        self.assertEqual(email.recipients[0].address, "shola@example.com")
        self.assertEqual(email.received_at.isoformat(), "2026-06-15T09:30:00+00:00")
        self.assertEqual(email.headers["list-id"], "updates.example.com")
        self.assertEqual(email.labels, ("INBOX", "CATEGORY_UPDATES"))

    def test_to_dict_is_json_serializable(self):
        sample = json.loads((FIXTURES_DIR / "sample_emails.json").read_text())[1]

        email = NormalizedEmail.from_mapping(sample)
        encoded = json.dumps(email.to_dict())

        self.assertIn("sample-outlook-001", encoded)
        self.assertEqual(email.to_dict()["received_at"], "2026-05-20T13:15:00Z")

    def test_requires_id_and_received_at(self):
        with self.assertRaises(ValueError):
            NormalizedEmail(
                id="",
                provider="sample",
                subject="Missing id",
                sender="sender@example.com",
                recipients=("recipient@example.com",),
                received_at="2026-06-15T09:30:00Z",
            )

        with self.assertRaises(ValueError):
            NormalizedEmail(
                id="sample-001",
                provider="sample",
                subject="Missing date",
                sender="sender@example.com",
                recipients=("recipient@example.com",),
                received_at="",
            )


if __name__ == "__main__":
    unittest.main()
