"""Provider-neutral email model for offline classification and policy tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping


class EmailProvider(str, Enum):
    """Supported email source providers."""

    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SAMPLE = "sample"


@dataclass(frozen=True)
class EmailContact:
    """A normalized email contact."""

    address: str
    name: str = ""

    def __post_init__(self) -> None:
        address = self.address.strip().lower()
        if not address:
            raise ValueError("contact address is required")
        object.__setattr__(self, "address", address)
        object.__setattr__(self, "name", self.name.strip())

    @classmethod
    def from_value(cls, value: Any) -> "EmailContact":
        """Build a contact from a fixture/provider mapping or raw address."""

        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(address=value)
        if isinstance(value, Mapping):
            return cls(
                address=str(value.get("address", "")),
                name=str(value.get("name", "")),
            )
        raise TypeError("contact must be a string or mapping")

    def to_dict(self) -> dict[str, str]:
        return {"address": self.address, "name": self.name}


@dataclass(frozen=True)
class NormalizedEmail:
    """A provider-neutral email shape for policy evaluation."""

    id: str
    provider: EmailProvider
    subject: str
    sender: EmailContact
    recipients: tuple[EmailContact, ...]
    received_at: datetime
    thread_id: str = ""
    cc: tuple[EmailContact, ...] = ()
    bcc: tuple[EmailContact, ...] = ()
    snippet: str = ""
    body_text: str = ""
    body_html: str = ""
    labels: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    headers: Mapping[str, str] = MappingProxyType({})
    is_read: bool = False
    is_starred: bool = False
    importance: str = "normal"

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("email id is required")

        provider = self.provider
        if not isinstance(provider, EmailProvider):
            provider = EmailProvider(str(provider).lower())

        received_at = _coerce_datetime(self.received_at)

        object.__setattr__(self, "id", str(self.id).strip())
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "subject", str(self.subject))
        object.__setattr__(self, "sender", EmailContact.from_value(self.sender))
        object.__setattr__(self, "recipients", _contacts_tuple(self.recipients))
        object.__setattr__(self, "received_at", received_at)
        object.__setattr__(self, "thread_id", str(self.thread_id))
        object.__setattr__(self, "cc", _contacts_tuple(self.cc))
        object.__setattr__(self, "bcc", _contacts_tuple(self.bcc))
        object.__setattr__(self, "snippet", str(self.snippet))
        object.__setattr__(self, "body_text", str(self.body_text))
        object.__setattr__(self, "body_html", str(self.body_html))
        object.__setattr__(self, "labels", _strings_tuple(self.labels))
        object.__setattr__(self, "categories", _strings_tuple(self.categories))
        object.__setattr__(self, "headers", MappingProxyType(_headers_dict(self.headers)))
        object.__setattr__(self, "is_read", bool(self.is_read))
        object.__setattr__(self, "is_starred", bool(self.is_starred))
        object.__setattr__(self, "importance", str(self.importance or "normal").lower())

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "NormalizedEmail":
        """Build a normalized email from a fixture/provider-neutral mapping."""

        return cls(
            id=data.get("id", ""),
            provider=data.get("provider", ""),
            subject=data.get("subject", ""),
            sender=data.get("sender", {}),
            recipients=tuple(data.get("recipients", ())),
            received_at=data.get("received_at", ""),
            thread_id=data.get("thread_id", ""),
            cc=tuple(data.get("cc", ())),
            bcc=tuple(data.get("bcc", ())),
            snippet=data.get("snippet", ""),
            body_text=data.get("body_text", ""),
            body_html=data.get("body_html", ""),
            labels=tuple(data.get("labels", ())),
            categories=tuple(data.get("categories", ())),
            headers=data.get("headers", {}),
            is_read=data.get("is_read", False),
            is_starred=data.get("is_starred", False),
            importance=data.get("importance", "normal"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "id": self.id,
            "provider": self.provider.value,
            "subject": self.subject,
            "sender": self.sender.to_dict(),
            "recipients": [contact.to_dict() for contact in self.recipients],
            "received_at": self.received_at.isoformat().replace("+00:00", "Z"),
            "thread_id": self.thread_id,
            "cc": [contact.to_dict() for contact in self.cc],
            "bcc": [contact.to_dict() for contact in self.bcc],
            "snippet": self.snippet,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "labels": list(self.labels),
            "categories": list(self.categories),
            "headers": dict(self.headers),
            "is_read": self.is_read,
            "is_starred": self.is_starred,
            "importance": self.importance,
        }


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("received_at is required")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _contacts_tuple(values: Iterable[Any]) -> tuple[EmailContact, ...]:
    return tuple(EmailContact.from_value(value) for value in values)


def _strings_tuple(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(value).strip() for value in values if str(value).strip())


def _headers_dict(headers: Mapping[str, Any]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}
