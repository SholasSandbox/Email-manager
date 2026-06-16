"""Markdown report rendering for safe policy decisions."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Mapping

from .models import NormalizedEmail
from .policy_engine import PolicyDecision


SECTION_BY_DISPOSITION = {
    "remind": "## Remind",
    "review": "## Review",
    "keep": "## Keep",
    "archive": "## Candidate Archive - Dry Run Only",
    "trash": "## Candidate Trash - Dry Run Only",
    "suppress": "## Suppression Candidates",
}
DISPOSITION_ORDER = ("remind", "review", "keep", "archive", "trash", "suppress")


def render_daily_review(
    decisions: list[PolicyDecision] | tuple[PolicyDecision, ...],
    emails_by_id: Mapping[str, NormalizedEmail | Mapping[str, Any]] | None = None,
) -> str:
    """Render a deterministic Markdown review report without writing files."""

    emails_by_id = emails_by_id or {}
    decisions_by_disposition = {
        disposition: sorted(
            [decision for decision in decisions if decision.disposition == disposition],
            key=lambda decision: (decision.provider, decision.message_id),
        )
        for disposition in DISPOSITION_ORDER
    }
    counts = Counter(decision.disposition for decision in decisions)
    executed_count = sum(1 for decision in decisions if decision.executed)

    lines = [
        "# Daily Mail Review",
        "",
        "Dry run report. No mailbox actions were executed.",
        "",
    ]

    for disposition in DISPOSITION_ORDER:
        lines.append(SECTION_BY_DISPOSITION[disposition])
        lines.append("")
        section_decisions = decisions_by_disposition[disposition]
        if not section_decisions:
            lines.append("- None")
        for decision in section_decisions:
            lines.append(_decision_line(decision, emails_by_id.get(decision.message_id)))
        lines.append("")

    lines.append("## Action Summary")
    lines.append("")
    for disposition in DISPOSITION_ORDER:
        lines.append(f"- {disposition}: {counts.get(disposition, 0)}")
    lines.append(f"- executed: {executed_count}")
    lines.append("")

    lines.append("## Errors / Warnings")
    lines.append("")
    if executed_count:
        lines.append(f"- Warning: {executed_count} decision(s) were marked executed.")
    else:
        lines.append("- No warnings. No mailbox actions were executed.")
    lines.append("")

    return "\n".join(lines)


def _decision_line(
    decision: PolicyDecision,
    email: NormalizedEmail | Mapping[str, Any] | None,
) -> str:
    metadata = _email_metadata(email)
    fields = [
        f"provider={decision.provider}",
        f"message_id={decision.message_id}",
    ]
    if metadata["from_address"]:
        fields.append(f"from_address={metadata['from_address']}")
    elif metadata["from_domain"]:
        fields.append(f"from_domain={metadata['from_domain']}")
    if metadata["subject"]:
        fields.append(f"subject={_clean(metadata['subject'])}")
    fields.extend(
        [
            f"disposition={decision.disposition}",
            f"reason_code={decision.reason_code}",
            f"confidence={decision.confidence:.2f}",
            f"policy_action={_stable_json(decision.policy_action)}",
            f"protected={decision.protected}",
            f"matched_rules={_stable_json(decision.matched_rules)}",
            f"executed={decision.executed}",
        ]
    )
    return "- " + "; ".join(fields)


def _email_metadata(email: NormalizedEmail | Mapping[str, Any] | None) -> dict[str, str | None]:
    if email is None:
        return {"from_address": None, "from_domain": None, "subject": None}
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
    address = address.strip().lower()
    return {
        "from_address": address or None,
        "from_domain": _domain(address),
        "subject": subject.strip() or None,
    }


def _domain(address: str) -> str | None:
    if "@" not in address:
        return None
    return address.rsplit("@", 1)[1] or None


def _clean(value: str) -> str:
    return " ".join(value.split())


def _stable_json(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value
