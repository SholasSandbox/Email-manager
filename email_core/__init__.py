"""Core, provider-neutral email primitives."""

from .models import EmailContact, EmailProvider, NormalizedEmail
from .audit_log import decision_to_audit_record, render_audit_jsonl
from .gmail_adapter import (
    GMAIL_METADATA_HEADERS,
    fetch_gmail_normalized_emails,
    get_gmail_message_metadata,
    list_gmail_message_ids,
    normalize_gmail_message,
)
from .policy_engine import PolicyDecision, evaluate_policy
from .policy_loader import EmailPolicy, PolicyAction, PolicyRule, load_policy, parse_policy
from .report_writer import render_daily_review

__all__ = [
    "EmailContact",
    "EmailPolicy",
    "EmailProvider",
    "GMAIL_METADATA_HEADERS",
    "NormalizedEmail",
    "PolicyDecision",
    "PolicyAction",
    "PolicyRule",
    "decision_to_audit_record",
    "evaluate_policy",
    "fetch_gmail_normalized_emails",
    "get_gmail_message_metadata",
    "list_gmail_message_ids",
    "load_policy",
    "normalize_gmail_message",
    "parse_policy",
    "render_audit_jsonl",
    "render_daily_review",
]
