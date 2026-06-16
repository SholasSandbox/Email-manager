"""Core, provider-neutral email primitives."""

from .models import EmailContact, EmailProvider, NormalizedEmail
from .audit_log import decision_to_audit_record, render_audit_jsonl
from .policy_engine import PolicyDecision, evaluate_policy
from .policy_loader import EmailPolicy, PolicyAction, PolicyRule, load_policy, parse_policy
from .report_writer import render_daily_review

__all__ = [
    "EmailContact",
    "EmailPolicy",
    "EmailProvider",
    "NormalizedEmail",
    "PolicyDecision",
    "PolicyAction",
    "PolicyRule",
    "decision_to_audit_record",
    "evaluate_policy",
    "load_policy",
    "parse_policy",
    "render_audit_jsonl",
    "render_daily_review",
]
