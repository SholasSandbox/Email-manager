import importlib
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


class FakeExecutable:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeMessagesResource:
    def __init__(self, list_pages, message_payloads):
        self.list_pages = list_pages
        self.message_payloads = message_payloads
        self.list_calls = []
        self.get_calls = []
        self.mutation_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        page_token = kwargs.get("pageToken")
        return FakeExecutable(self.list_pages[page_token])

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        message_id = kwargs["id"]
        return FakeExecutable(self.message_payloads[message_id])

    def __getattr__(self, name):
        if name in {"modify", "trash", "delete", "batchModify", "send", "insert", "import"}:
            self.mutation_calls.append(name)
            raise AssertionError(f"unexpected Gmail mutation method access: {name}")
        raise AttributeError(name)


class FakeUsersResource:
    def __init__(self, messages_resource):
        self.messages_resource = messages_resource

    def messages(self):
        return self.messages_resource


class FakeGmailService:
    def __init__(self, list_pages, message_payloads):
        self.messages_resource = FakeMessagesResource(list_pages, message_payloads)

    def users(self):
        return FakeUsersResource(self.messages_resource)


def make_gmail_message(
    message_id="gmail-001",
    *,
    thread_id="thread-001",
    from_header="Example Sender <sender@example.com>",
    to_header="Shola <shola@example.com>",
    cc_header="Team <team@example.com>",
    subject="Metadata subject",
    date_header="Tue, 16 Jun 2026 10:30:00 +0000",
    snippet="Snippet text",
    label_ids=None,
    extra_headers=None,
    internal_date="1781605800000",
):
    headers = [
        {"name": "From", "value": from_header},
        {"name": "To", "value": to_header},
        {"name": "Subject", "value": subject},
        {"name": "Date", "value": date_header},
    ]
    if cc_header is not None:
        headers.append({"name": "Cc", "value": cc_header})
    for name, value in (extra_headers or {}).items():
        headers.append({"name": name, "value": value})
    return {
        "id": message_id,
        "threadId": thread_id,
        "labelIds": label_ids or ["INBOX"],
        "snippet": snippet,
        "internalDate": internal_date,
        "payload": {"headers": headers},
    }


class GmailAdapterTests(unittest.TestCase):
    def test_normalize_gmail_message_maps_metadata_to_normalized_email(self):
        from email_core.gmail_adapter import normalize_gmail_message

        message = make_gmail_message(
            label_ids=["INBOX", "UNREAD", "STARRED", "IMPORTANT", "CATEGORY_UPDATES"],
            extra_headers={
                "Reply-To": "reply@example.com",
                "List-Unsubscribe": "<mailto:unsubscribe@example.com>",
                "List-ID": "updates.example.com",
            },
        )

        email = normalize_gmail_message(message, user_email="shola@example.com")

        self.assertEqual(email.id, "gmail-001")
        self.assertEqual(email.provider.value, "gmail")
        self.assertEqual(email.thread_id, "thread-001")
        self.assertEqual(email.subject, "Metadata subject")
        self.assertEqual(email.sender.address, "sender@example.com")
        self.assertEqual(email.sender.name, "Example Sender")
        self.assertEqual(email.headers["x-gmail-from-domain"], "example.com")
        self.assertEqual([contact.address for contact in email.recipients], ["shola@example.com"])
        self.assertEqual([contact.address for contact in email.cc], ["team@example.com"])
        self.assertEqual(email.snippet, "Snippet text")
        self.assertEqual(email.labels, ("INBOX", "UNREAD", "STARRED", "IMPORTANT", "CATEGORY_UPDATES"))
        self.assertEqual(email.categories, ("CATEGORY_UPDATES",))
        self.assertFalse(email.is_read)
        self.assertTrue(email.is_starred)
        self.assertEqual(email.importance, "important")
        self.assertEqual(email.headers["list-unsubscribe"], "<mailto:unsubscribe@example.com>")
        self.assertEqual(email.headers["list-id"], "updates.example.com")
        self.assertEqual(email.headers["x-gmail-is-direct-to-me"], "true")
        self.assertEqual(email.headers["x-gmail-is-unread"], "true")
        self.assertEqual(email.headers["x-gmail-has-list-unsubscribe"], "true")
        self.assertEqual(email.headers["x-gmail-has-list-id"], "true")

    def test_normalize_gmail_message_handles_missing_optional_headers_and_snippet(self):
        from email_core.gmail_adapter import normalize_gmail_message

        message = make_gmail_message(cc_header=None, snippet=None, extra_headers={})
        del message["snippet"]

        email = normalize_gmail_message(message)

        self.assertEqual(email.cc, ())
        self.assertEqual(email.snippet, "")
        self.assertEqual(email.headers["x-gmail-has-list-unsubscribe"], "false")
        self.assertEqual(email.headers["x-gmail-has-list-id"], "false")

    def test_normalize_gmail_message_marks_direct_to_me_when_user_is_only_in_cc(self):
        from email_core.gmail_adapter import normalize_gmail_message

        message = make_gmail_message(
            to_header="Someone Else <other@example.com>",
            cc_header="Shola <shola@example.com>",
        )

        email = normalize_gmail_message(message, user_email="shola@example.com")

        self.assertEqual(email.headers["x-gmail-is-direct-to-me"], "true")

    def test_normalize_gmail_message_marks_direct_to_me_false_when_user_absent(self):
        from email_core.gmail_adapter import normalize_gmail_message

        message = make_gmail_message(
            to_header="Someone Else <other@example.com>",
            cc_header="Team <team@example.com>",
        )

        email = normalize_gmail_message(message, user_email="shola@example.com")

        self.assertEqual(email.headers["x-gmail-is-direct-to-me"], "false")

    def test_normalize_gmail_message_uses_internal_date_when_date_header_is_malformed(self):
        from email_core.gmail_adapter import normalize_gmail_message

        message = make_gmail_message(date_header="definitely not a real date")

        email = normalize_gmail_message(message)

        self.assertEqual(email.received_at, datetime.fromtimestamp(1781605800, tz=timezone.utc))

    def test_list_gmail_message_ids_calls_read_only_list_and_handles_pagination(self):
        from email_core.gmail_adapter import list_gmail_message_ids

        service = FakeGmailService(
            list_pages={
                None: {
                    "messages": [{"id": "gmail-001"}, {"id": "gmail-002"}],
                    "nextPageToken": "page-2",
                },
                "page-2": {"messages": [{"id": "gmail-003"}]},
            },
            message_payloads={},
        )

        message_ids = list_gmail_message_ids(
            service,
            user_id="me",
            query="label:inbox",
            max_results=3,
        )

        self.assertEqual(message_ids, ["gmail-001", "gmail-002", "gmail-003"])
        self.assertEqual(
            service.messages_resource.list_calls,
            [
                {
                    "userId": "me",
                    "maxResults": 3,
                    "includeSpamTrash": False,
                    "q": "label:inbox",
                },
                {
                    "userId": "me",
                    "maxResults": 1,
                    "includeSpamTrash": False,
                    "pageToken": "page-2",
                    "q": "label:inbox",
                },
            ],
        )

    def test_list_gmail_message_ids_respects_max_results(self):
        from email_core.gmail_adapter import list_gmail_message_ids

        service = FakeGmailService(
            list_pages={
                None: {
                    "messages": [
                        {"id": "gmail-001"},
                        {"id": "gmail-002"},
                        {"id": "gmail-003"},
                    ],
                    "nextPageToken": "page-2",
                },
                "page-2": {"messages": [{"id": "gmail-004"}]},
            },
            message_payloads={},
        )

        message_ids = list_gmail_message_ids(service, max_results=2)

        self.assertEqual(message_ids, ["gmail-001", "gmail-002"])
        self.assertEqual(len(service.messages_resource.list_calls), 1)

    def test_get_gmail_message_metadata_uses_metadata_format_and_safe_headers(self):
        from email_core.gmail_adapter import GMAIL_METADATA_HEADERS, get_gmail_message_metadata

        payload = make_gmail_message()
        service = FakeGmailService(list_pages={None: {"messages": []}}, message_payloads={"gmail-001": payload})

        result = get_gmail_message_metadata(service, "gmail-001", user_id="me")

        self.assertEqual(result["id"], "gmail-001")
        self.assertEqual(
            service.messages_resource.get_calls,
            [
                {
                    "userId": "me",
                    "id": "gmail-001",
                    "format": "metadata",
                    "metadataHeaders": GMAIL_METADATA_HEADERS,
                }
            ],
        )

    def test_fetch_gmail_normalized_emails_returns_one_email_per_message(self):
        from email_core.gmail_adapter import fetch_gmail_normalized_emails

        message_one = make_gmail_message(message_id="gmail-001")
        message_two = make_gmail_message(
            message_id="gmail-002",
            thread_id="thread-002",
            label_ids=["CATEGORY_PROMOTIONS"],
        )
        service = FakeGmailService(
            list_pages={None: {"messages": [{"id": "gmail-001"}, {"id": "gmail-002"}]}},
            message_payloads={"gmail-001": message_one, "gmail-002": message_two},
        )

        emails = fetch_gmail_normalized_emails(service, user_email="shola@example.com", max_results=5)

        self.assertEqual([email.id for email in emails], ["gmail-001", "gmail-002"])
        self.assertEqual(emails[1].categories, ("CATEGORY_PROMOTIONS",))

    def test_fetch_gmail_normalized_emails_never_touches_mutation_methods(self):
        from email_core.gmail_adapter import fetch_gmail_normalized_emails

        payload = make_gmail_message()
        service = FakeGmailService(
            list_pages={None: {"messages": [{"id": "gmail-001"}]}},
            message_payloads={"gmail-001": payload},
        )

        fetch_gmail_normalized_emails(service)

        self.assertEqual(service.messages_resource.mutation_calls, [])

    def test_adapter_module_does_not_import_outlook_or_ollama_modules(self):
        importlib.import_module("email_core.gmail_adapter")

        source = Path(__file__).resolve().parents[1] / "email_core" / "gmail_adapter.py"
        source_text = source.read_text(encoding="utf-8").lower()

        self.assertNotIn("outlook_handler", sys.modules)
        self.assertNotIn("ollama", sys.modules)
        self.assertNotIn("openclaw", sys.modules)
        self.assertNotIn("outlook_handler", source_text)
        self.assertNotIn("ollama", source_text)
        self.assertNotIn("openclaw", source_text)


if __name__ == "__main__":
    unittest.main()
