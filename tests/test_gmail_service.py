import tempfile
import unittest
from builtins import __import__ as builtin_import
from pathlib import Path
from unittest.mock import patch


class GmailServiceTests(unittest.TestCase):
    def test_build_service_raises_helpful_error_when_google_clients_missing(self):
        from email_core.gmail_service import build_gmail_readonly_service

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.startswith("google.") or name.startswith("google_auth_oauthlib") or name.startswith("googleapiclient"):
                raise ModuleNotFoundError("No module named 'googleapiclient'")
            return builtin_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(ImportError) as error:
                build_gmail_readonly_service()

        self.assertIn("pip install -r requirements.txt", str(error.exception))
        self.assertIn("google-api-python-client", str(error.exception))
        self.assertIn("gmail.readonly", str(error.exception))

    def test_build_service_raises_helpful_error_when_credentials_file_is_missing(self):
        from email_core.gmail_service import build_gmail_readonly_service

        fake_clients = (
            object(),
            type("FakeFlow", (), {"from_client_secrets_file": object()}),
            object(),
        )
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "email_core.gmail_service._load_google_client_modules",
            return_value=fake_clients,
        ):
            missing_credentials = Path(tmpdir) / "missing-gmail-credentials.json"
            with self.assertRaises(FileNotFoundError) as error:
                build_gmail_readonly_service(credentials_path=missing_credentials)

        self.assertIn(str(missing_credentials), str(error.exception))
        self.assertIn("Desktop app OAuth", str(error.exception))
        self.assertIn("gmail_credentials.json", str(error.exception))


if __name__ == "__main__":
    unittest.main()
