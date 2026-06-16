"""Read-only Gmail metadata adapter for the provider-neutral email model."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any, Mapping

from .models import EmailProvider, NormalizedEmail


GMAIL_METADATA_HEADERS = [
    "From",
    "To",
    "Cc",
    "Subject",
    "Date",
    "List-Unsubscribe",
    "List-ID",
    "Precedence",
    "Auto-Submitted",
    "Reply-To",
]

_DEFAULT_SENDER_ADDRESS = "unknown@invalid"
_EPOCH_UTC = datetime.fromtimestamp(0, tz=timezone.utc)


def normalize_gmail_message(message: dict, user_email: str | None = None) -> NormalizedEmail:
    """Convert a Gmail metadata payload into the existing normalized email model."""

    header_values = _extract_header_values(message)
    sender = _parse_sender(header_values.get("from", ""))
    recipients = _parse_contacts(header_values.get("to", ""))
    cc = _parse_contacts(header_values.get("cc", ""))
    label_ids = _extract_label_ids(message)
    direct_to_me = _is_direct_to_me(user_email, recipients, cc)

    headers = dict(header_values)
    headers["x-gmail-from-domain"] = _sender_domain(sender["address"])
    headers["x-gmail-is-direct-to-me"] = _bool_text(direct_to_me)
    headers["x-gmail-is-unread"] = _bool_text("UNREAD" in label_ids)
    headers["x-gmail-has-list-unsubscribe"] = _bool_text("list-unsubscribe" in header_values)
    headers["x-gmail-has-list-id"] = _bool_text("list-id" in header_values)
    headers["x-gmail-has-attachment"] = _bool_text(_has_attachment_metadata(message))

    return NormalizedEmail(
        id=str(message.get("id", "")),
        provider=EmailProvider.GMAIL,
        subject=header_values.get("subject", ""),
        sender=sender,
        recipients=recipients,
        received_at=_parse_received_at(message, header_values.get("date", "")),
        thread_id=str(message.get("threadId", "")),
        cc=cc,
        snippet=str(message.get("snippet", "") or ""),
        labels=label_ids,
        categories=tuple(label for label in label_ids if label.startswith("CATEGORY_")),
        headers=headers,
        is_read="UNREAD" not in label_ids,
        is_starred="STARRED" in label_ids,
        importance="important" if "IMPORTANT" in label_ids else "normal",
    )


def list_gmail_message_ids(
    service,
    user_id: str = "me",
    query: str | None = None,
    max_results: int = 50,
) -> list[str]:
    """List Gmail message ids using read-only list calls only."""

    remaining = max(0, int(max_results))
    if remaining == 0:
        return []

    message_ids: list[str] = []
    page_token: str | None = None
    while remaining > 0:
        request_args: dict[str, Any] = {
            "userId": user_id,
            "maxResults": min(remaining, 500),
            "includeSpamTrash": False,
        }
        if page_token:
            request_args["pageToken"] = page_token
        if query:
            request_args["q"] = query

        response = service.users().messages().list(**request_args).execute()
        messages = response.get("messages", ())
        for item in messages:
            message_id = str(item.get("id", "")).strip()
            if message_id:
                message_ids.append(message_id)
                remaining -= 1
                if remaining == 0:
                    break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return message_ids


def get_gmail_message_metadata(service, message_id: str, user_id: str = "me") -> dict:
    """Fetch Gmail message metadata without retrieving bodies or attachments."""

    return service.users().messages().get(
        userId=user_id,
        id=message_id,
        format="metadata",
        metadataHeaders=GMAIL_METADATA_HEADERS,
    ).execute()


def fetch_gmail_normalized_emails(
    service,
    user_email: str | None = None,
    user_id: str = "me",
    query: str | None = None,
    max_results: int = 50,
) -> list[NormalizedEmail]:
    """List Gmail message ids, fetch read-only metadata, and normalize each message."""

    message_ids = list_gmail_message_ids(
        service,
        user_id=user_id,
        query=query,
        max_results=max_results,
    )
    emails = []
    for message_id in message_ids:
        metadata = get_gmail_message_metadata(service, message_id, user_id=user_id)
        emails.append(normalize_gmail_message(metadata, user_email=user_email))
    return emails


def _extract_header_values(message: Mapping[str, Any]) -> dict[str, str]:
    payload = message.get("payload")
    if not isinstance(payload, Mapping):
        return {}

    raw_headers = payload.get("headers", ())
    header_values: dict[str, str] = {}
    for item in raw_headers:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name", "")).strip().lower()
        value = str(item.get("value", "")).strip()
        if name and value:
            header_values[name] = value
    return header_values


def _extract_label_ids(message: Mapping[str, Any]) -> tuple[str, ...]:
    raw_labels = message.get("labelIds", ())
    if not isinstance(raw_labels, (list, tuple)):
        return ()
    return tuple(str(label).strip() for label in raw_labels if str(label).strip())


def _parse_sender(raw_value: str) -> dict[str, str]:
    name, address = parseaddr(raw_value or "")
    clean_address = (address or _DEFAULT_SENDER_ADDRESS).strip().lower()
    clean_name = name.strip() or (raw_value.strip() if not address else "")
    return {"address": clean_address, "name": clean_name}


def _parse_contacts(raw_value: str) -> tuple[dict[str, str], ...]:
    contacts = []
    for name, address in getaddresses([raw_value or ""]):
        clean_address = address.strip().lower()
        if not clean_address:
            continue
        contacts.append({"address": clean_address, "name": name.strip()})
    return tuple(contacts)


def _parse_received_at(message: Mapping[str, Any], raw_date: str) -> datetime:
    if raw_date:
        try:
            parsed = parsedate_to_datetime(raw_date)
        except (TypeError, ValueError, IndexError, OverflowError):
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)

    internal_date = message.get("internalDate")
    try:
        return datetime.fromtimestamp(int(str(internal_date)) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return _EPOCH_UTC


def _is_direct_to_me(
    user_email: str | None,
    recipients: tuple[dict[str, str], ...],
    cc: tuple[dict[str, str], ...],
) -> bool:
    if not user_email:
        return False
    target = user_email.strip().lower()
    addresses = {contact["address"] for contact in recipients}
    addresses.update(contact["address"] for contact in cc)
    return target in addresses


def _sender_domain(address: str) -> str:
    if "@" not in address:
        return ""
    return address.rsplit("@", 1)[1]


def _has_attachment_metadata(message: Mapping[str, Any]) -> bool:
    payload = message.get("payload")
    if not isinstance(payload, Mapping):
        return False

    if str(payload.get("filename", "")).strip():
        return True

    parts = payload.get("parts", ())
    if not isinstance(parts, (list, tuple)):
        return False

    for part in parts:
        if not isinstance(part, Mapping):
            continue
        if str(part.get("filename", "")).strip():
            return True
    return False


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
