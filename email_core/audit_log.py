"""JSONL audit rendering for safe policy decisions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

from .models import NormalizedEmail
from .policy_engine import PolicyDecision


def decision_to_audit_record(
    decision: PolicyDecision,
    email: NormalizedEmail | Mapping[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Convert a policy decision into a JSON-safe audit record."""

    metadata = _email_metadata(email)
    return {
        "timestamp": timestamp or _utc_timestamp(),
        "provider": decision.provider,
        "message_id": decision.message_id,
        "from_domain": metadata["from_domain"],
        "subject": metadata["subject"],
        "disposition": decision.disposition,
        "reason_code": decision.reason_code,
        "confidence": decision.confidence,
        "policy_action": _json_safe(decision.policy_action),
        "mode": decision.mode,
        "executed": decision.executed,
        "protected": decision.protected,
        "matched_rules": list(decision.matched_rules),
    }


def render_audit_jsonl(records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> str:
    """Render JSONL with one valid JSON object per line."""

    if not records:
        return ""
    return "\n".join(json.dumps(_json_safe(record), sort_keys=True) for record in records) + "\n"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _email_metadata(email: NormalizedEmail | Mapping[str, Any] | None) -> dict[str, str | None]:
    if email is None:
        return {"from_domain": None, "subject": None}
    if isinstance(email, NormalizedEmail):
        address = email.sender.address
        subject = email.subject
    else:
        sender = email.get("sender", {})
        if isinstance(sender, Mapping):
            address = str(sender.get("address", ""))
        else:
            address = str(sender)
        subject = str(email.get("subject", ""))
    return {
        "from_domain": _domain(address.strip().lower()),
        "subject": " ".join(subject.split()) or None,
    }


def _domain(address: str) -> str | None:
    if "@" not in address:
        return None
    return address.rsplit("@", 1)[1] or None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value
