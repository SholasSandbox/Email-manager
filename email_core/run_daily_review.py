"""Local dry-run CLI for fixture-backed policy evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .audit_log import decision_to_audit_record, render_audit_jsonl
from .models import NormalizedEmail
from .policy_engine import evaluate_policy
from .policy_loader import load_policy
from .report_writer import render_daily_review


@dataclass(frozen=True)
class RunSummary:
    emails_processed: int
    decisions_produced: int
    report_path: Path
    audit_path: Path
    mode: str = "dry_run"


def load_sample_emails(path: str | Path) -> list[NormalizedEmail]:
    """Load normalized emails from a fixture JSON file."""

    data = _load_json(path)
    if not isinstance(data, list):
        raise ValueError(f"email fixture must be a list: {path}")
    emails = []
    for item in data:
        if not isinstance(item, Mapping):
            raise ValueError(f"email fixture entries must be mappings: {path}")
        emails.append(NormalizedEmail.from_mapping(item))
    return emails


def run_dry_review(
    emails_path: str | Path,
    policy_path: str | Path,
    report_path: str | Path,
    audit_path: str | Path,
) -> RunSummary:
    """Load fixture inputs, render dry-run outputs, and write them to disk."""

    emails = load_sample_emails(emails_path)
    policy = load_policy(policy_path)
    decisions = [evaluate_policy(email, policy) for email in emails]

    report_path = Path(report_path)
    audit_path = Path(audit_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    emails_by_id = {email.id: email for email in emails}
    report_text = render_daily_review(decisions, emails_by_id=emails_by_id)
    audit_records = [
        decision_to_audit_record(decision, email=emails_by_id.get(decision.message_id))
        for decision in decisions
    ]
    audit_text = render_audit_jsonl(audit_records)

    report_path.write_text(report_text, encoding="utf-8")
    audit_path.write_text(audit_text, encoding="utf-8")

    return RunSummary(
        emails_processed=len(emails),
        decisions_produced=len(decisions),
        report_path=report_path,
        audit_path=audit_path,
        mode="dry_run",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a local dry-run mail review from fixtures.")
    parser.add_argument("--emails", required=True, help="Path to sample email fixture JSON.")
    parser.add_argument("--policy", required=True, help="Path to policy fixture JSON.")
    parser.add_argument(
        "--report",
        default="reports/daily-review.md",
        help="Path to write the Markdown report.",
    )
    parser.add_argument(
        "--audit",
        default="runs/audit-log.jsonl",
        help="Path to write the audit JSONL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode. This is the default behavior.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Rejected in Phase 1D. Live mailbox actions are not implemented.",
    )
    args = parser.parse_args(argv)

    if args.live:
        print("Error: live mode is not available in Phase 1D.", file=sys.stderr)
        return 2

    try:
        summary = run_dry_review(
            emails_path=args.emails,
            policy_path=args.policy,
            report_path=args.report,
            audit_path=args.audit,
        )
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(
        "Dry-run complete: "
        f"processed {summary.emails_processed} email(s), "
        f"produced {summary.decisions_produced} decision(s), "
        f"wrote report to {summary.report_path}, "
        f"wrote audit log to {summary.audit_path}."
    )
    return 0


def _load_json(path: str | Path) -> Any:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    raise SystemExit(main())
