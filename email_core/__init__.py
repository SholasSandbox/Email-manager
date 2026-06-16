"""Core, provider-neutral email primitives."""

from .models import EmailContact, EmailProvider, NormalizedEmail
from .policy_engine import PolicyDecision, evaluate_policy
from .policy_loader import EmailPolicy, PolicyAction, PolicyRule, load_policy, parse_policy

__all__ = [
    "EmailContact",
    "EmailPolicy",
    "EmailProvider",
    "NormalizedEmail",
    "PolicyDecision",
    "PolicyAction",
    "PolicyRule",
    "evaluate_policy",
    "load_policy",
    "parse_policy",
]
