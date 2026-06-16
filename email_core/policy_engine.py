"""Pure safe-disposition policy engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from .models import NormalizedEmail
from .policy_loader import EmailPolicy


DISPOSITIONS = frozenset({"remind", "review", "keep", "archive", "trash", "suppress"})
DESTRUCTIVE_DISPOSITIONS = frozenset({"archive", "trash", "suppress"})
REASON_CODES = frozenset(
    {
        "direct_personal_request",
        "application_update",
        "interview_or_recruiter",
        "security_or_account",
        "payment_or_invoice",
        "calendar_or_meeting",
        "generic_newsletter",
        "generic_promotion",
        "job_alert",
        "rejection_notice",
        "automated_notification",
        "unknown",
    }
)
DEFAULT_THRESHOLDS = {
    "newsletter_days": 30,
    "promotion_days": 30,
    "job_alert_days": 7,
}
DESTRUCTIVE_CONFIDENCE_THRESHOLD = 0.8


@dataclass(frozen=True)
class PolicyDecision:
    """The single safe disposition decision for a normalized email."""

    message_id: str
    provider: str
    disposition: str
    reason_code: str
    confidence: float
    policy_action: Mapping[str, Any]
    executed: bool
    mode: str
    protected: bool
    matched_rules: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.disposition not in DISPOSITIONS:
            raise ValueError(f"unsupported disposition: {self.disposition}")
        if self.reason_code not in REASON_CODES:
            raise ValueError(f"unsupported reason_code: {self.reason_code}")
        object.__setattr__(self, "policy_action", MappingProxyType(dict(self.policy_action)))
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "executed", bool(self.executed))
        object.__setattr__(self, "protected", bool(self.protected))
        object.__setattr__(self, "matched_rules", tuple(self.matched_rules))


@dataclass(frozen=True)
class _DeterministicDecision:
    disposition: str
    reason_code: str
    confidence: float
    policy_action: Mapping[str, Any]
    protected: bool = False


@dataclass(frozen=True)
class _ClassifierDecision:
    disposition: str
    reason_code: str
    confidence: float


def evaluate_policy(
    email: NormalizedEmail,
    policy: EmailPolicy,
    classifier_result: Mapping[str, Any] | None = None,
) -> PolicyDecision:
    """Evaluate one email and return one safe, unexecuted disposition."""

    matched_rules = _matched_policy_rules(email, policy)
    thresholds = _retention_thresholds(policy)
    mode = _policy_mode(policy)
    destructive_confidence_threshold = _destructive_confidence_threshold(policy)

    protected_decision = _protection_decision(email)
    if protected_decision:
        return _decision(email, protected_decision, matched_rules, mode)

    deterministic_decision = _cleanup_decision(email, thresholds)
    classifier_decision, classifier_status = _classifier_decision(classifier_result)

    if classifier_result is not None:
        if classifier_status != "valid":
            return _fail_closed(email, matched_rules, classifier_status, mode)
        if classifier_decision.disposition == "suppress":
            return _fail_closed(email, matched_rules, "suppression_out_of_scope", mode)
        if (
            classifier_decision.disposition in DESTRUCTIVE_DISPOSITIONS
            and classifier_decision.confidence < destructive_confidence_threshold
        ):
            return _fail_closed(email, matched_rules, "low_confidence", mode)
        if classifier_decision.disposition in DESTRUCTIVE_DISPOSITIONS:
            if (
                deterministic_decision
                and deterministic_decision.disposition == classifier_decision.disposition
            ):
                return _decision(
                    email,
                    _DeterministicDecision(
                        disposition=deterministic_decision.disposition,
                        reason_code=deterministic_decision.reason_code,
                        confidence=classifier_decision.confidence,
                        policy_action={
                            **dict(deterministic_decision.policy_action),
                            "source": "policy_and_classifier",
                        },
                    ),
                    matched_rules,
                    mode,
                )
            return _fail_closed(email, matched_rules, "requires_deterministic_support", mode)
        return _decision(
            email,
            _DeterministicDecision(
                disposition=classifier_decision.disposition,
                reason_code=classifier_decision.reason_code,
                confidence=classifier_decision.confidence,
                policy_action={"source": "classifier", "status": "accepted"},
            ),
            matched_rules,
            mode,
        )

    if deterministic_decision:
        return _decision(email, deterministic_decision, matched_rules, mode)

    return _fail_closed(email, matched_rules, "no_match", mode)


def _decision(
    email: NormalizedEmail,
    candidate: _DeterministicDecision,
    matched_rules: tuple[str, ...],
    mode: str,
) -> PolicyDecision:
    return PolicyDecision(
        message_id=email.id,
        provider=email.provider.value,
        disposition=candidate.disposition,
        reason_code=candidate.reason_code,
        confidence=candidate.confidence,
        policy_action=candidate.policy_action,
        executed=False,
        mode=mode,
        protected=candidate.protected,
        matched_rules=matched_rules,
    )


def _fail_closed(
    email: NormalizedEmail,
    matched_rules: tuple[str, ...],
    status: str,
    mode: str,
) -> PolicyDecision:
    return PolicyDecision(
        message_id=email.id,
        provider=email.provider.value,
        disposition="review",
        reason_code="unknown",
        confidence=0.0,
        policy_action={"source": "policy_engine", "status": status},
        executed=False,
        mode=mode,
        protected=False,
        matched_rules=matched_rules,
    )


def _policy_mode(policy: EmailPolicy) -> str:
    return str(policy.mode or "dry_run").strip() or "dry_run"


def _destructive_confidence_threshold(policy: EmailPolicy) -> float:
    value = policy.destructive_confidence_threshold
    if value is None or isinstance(value, bool):
        return DESTRUCTIVE_CONFIDENCE_THRESHOLD
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DESTRUCTIVE_CONFIDENCE_THRESHOLD
    if parsed < DESTRUCTIVE_CONFIDENCE_THRESHOLD or parsed > 1.0:
        return DESTRUCTIVE_CONFIDENCE_THRESHOLD
    return parsed


def _retention_thresholds(policy: EmailPolicy) -> dict[str, int]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    for key in DEFAULT_THRESHOLDS:
        value = policy.retention_thresholds.get(key)
        if isinstance(value, bool):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            thresholds[key] = parsed
    return thresholds


def _classifier_decision(
    classifier_result: Mapping[str, Any] | None,
) -> tuple[_ClassifierDecision | None, str]:
    if classifier_result is None:
        return None, "absent"
    if not isinstance(classifier_result, Mapping):
        return None, "invalid_classifier"

    disposition = str(classifier_result.get("disposition", "")).strip().lower()
    reason_code = str(classifier_result.get("reason_code", "")).strip().lower()
    confidence = classifier_result.get("confidence")

    if disposition not in DISPOSITIONS or reason_code not in REASON_CODES:
        return None, "invalid_classifier"
    if confidence is None:
        return None, "missing_confidence"
    if isinstance(confidence, bool):
        return None, "invalid_classifier"
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        return None, "invalid_classifier"
    if confidence < 0.0 or confidence > 1.0:
        return None, "invalid_classifier"

    return _ClassifierDecision(disposition, reason_code, confidence), "valid"


def _protection_decision(email: NormalizedEmail) -> _DeterministicDecision | None:
    text = _search_text(email)

    if _has_any(text, ("security alert", "account alert", "verify your account", "password reset")):
        return _protected("security_or_account")
    if _has_any(text, ("payment", "invoice", "billing", "receipt", "charge failed")):
        return _protected("payment_or_invoice")
    if _has_any(text, ("interview", "recruiter", "hiring manager", "schedule a call")):
        return _protected("interview_or_recruiter")
    if _has_any(text, ("meeting", "calendar", "appointment", "invite")):
        return _protected("calendar_or_meeting")
    if _is_application_update(email, text):
        return _protected("application_update")
    if _is_direct_personal_request(email, text):
        return _protected("direct_personal_request")
    return None


def _protected(reason_code: str) -> _DeterministicDecision:
    return _DeterministicDecision(
        disposition="review",
        reason_code=reason_code,
        confidence=1.0,
        policy_action={"source": "deterministic_policy", "status": "protected"},
        protected=True,
    )


def _cleanup_decision(
    email: NormalizedEmail,
    thresholds: Mapping[str, int],
) -> _DeterministicDecision | None:
    text = _search_text(email)
    age_days = _age_days(email)

    if _is_rejection_notice(text):
        return _DeterministicDecision(
            disposition="archive",
            reason_code="rejection_notice",
            confidence=1.0,
            policy_action={"source": "deterministic_policy", "threshold_days": None},
        )
    if _is_job_alert(email, text) and age_days >= thresholds["job_alert_days"]:
        return _DeterministicDecision(
            disposition="trash",
            reason_code="job_alert",
            confidence=1.0,
            policy_action={
                "source": "deterministic_policy",
                "threshold_days": thresholds["job_alert_days"],
            },
        )
    if _is_newsletter(email, text) and age_days >= thresholds["newsletter_days"]:
        return _DeterministicDecision(
            disposition="trash",
            reason_code="generic_newsletter",
            confidence=1.0,
            policy_action={
                "source": "deterministic_policy",
                "threshold_days": thresholds["newsletter_days"],
            },
        )
    if _is_promotion(email, text) and age_days >= thresholds["promotion_days"]:
        return _DeterministicDecision(
            disposition="trash",
            reason_code="generic_promotion",
            confidence=1.0,
            policy_action={
                "source": "deterministic_policy",
                "threshold_days": thresholds["promotion_days"],
            },
        )
    if _is_automated_notification(email, text):
        return _DeterministicDecision(
            disposition="review",
            reason_code="automated_notification",
            confidence=0.6,
            policy_action={"source": "deterministic_policy", "status": "weak_signal"},
        )
    return None


def _age_days(email: NormalizedEmail) -> int:
    now = datetime.now(timezone.utc)
    return max(0, (now - email.received_at).days)


def _is_newsletter(email: NormalizedEmail, text: str) -> bool:
    headers = email.headers
    return (
        "list-id" in headers
        or "list-unsubscribe" in headers
        or "newsletter" in text
        or "unsubscribe" in text
    )


def _is_promotion(email: NormalizedEmail, text: str) -> bool:
    labels = _lower_set(email.labels)
    categories = _lower_set(email.categories)
    return (
        "category_promotions" in labels
        or "promotions" in categories
        or _has_any(text, ("limited time offer", "sale", "discount", "promotion", "promo"))
    )


def _is_job_alert(email: NormalizedEmail, text: str) -> bool:
    sender = email.sender.address
    return (
        _has_any(text, ("job alert", "job alerts", "recommended jobs", "new jobs"))
        or sender.endswith("linkedin.com")
        or sender.endswith("indeed.com")
        or sender.endswith("glassdoor.com")
    )


def _is_rejection_notice(text: str) -> bool:
    return _has_any(
        text,
        (
            "regret to inform",
            "not moving forward",
            "not been successful",
            "pursue other candidates",
            "position has been filled",
        ),
    )


def _is_application_update(email: NormalizedEmail, text: str) -> bool:
    labels = _lower_set(email.labels)
    return (
        "category_promotions" in labels
        and _has_any(
            text,
            (
                "application",
                "next step",
                "complete your application",
                "application status",
                "assessment",
            ),
        )
        and not _is_rejection_notice(text)
    )


def _is_direct_personal_request(email: NormalizedEmail, text: str) -> bool:
    if _is_bulk_sender(email.sender.address) or _is_newsletter(email, text):
        return False
    return _has_any(
        text,
        (
            "hi shola",
            "could you",
            "can you",
            "please review",
            "please send",
            "please confirm",
        ),
    )


def _is_automated_notification(email: NormalizedEmail, text: str) -> bool:
    return _is_bulk_sender(email.sender.address) or _has_any(text, ("notification", "noreply", "no-reply"))


def _is_bulk_sender(address: str) -> bool:
    address = address.lower()
    return any(part in address for part in ("noreply", "no-reply", "notifications", "newsletter"))


def _search_text(email: NormalizedEmail) -> str:
    parts = [
        email.subject,
        email.sender.address,
        email.sender.name,
        email.snippet,
        email.body_text,
        " ".join(email.labels),
        " ".join(email.categories),
        " ".join(f"{key} {value}" for key, value in email.headers.items()),
    ]
    return " ".join(parts).lower()


def _lower_set(values: tuple[str, ...]) -> set[str]:
    return {value.lower() for value in values}


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _matched_policy_rules(email: NormalizedEmail, policy: EmailPolicy) -> tuple[str, ...]:
    matches = []
    for rule in policy.rules:
        if _matches_criteria(email, rule.criteria):
            matches.append(rule.name)
    return tuple(matches)


def _matches_criteria(email: NormalizedEmail, criteria: Mapping[str, Any]) -> bool:
    if "all" in criteria:
        return all(_matches_criteria(email, item) for item in criteria["all"])
    if "any" in criteria:
        return any(_matches_criteria(email, item) for item in criteria["any"])

    field = criteria.get("field")
    if not field:
        raise ValueError("criterion field is required")
    value = _field_value(email, str(field))

    operators = {"equals", "contains", "contains_any", "exists"}.intersection(criteria)
    if len(operators) != 1:
        raise ValueError("criterion must define exactly one supported operator")

    operator = operators.pop()
    expected = criteria[operator]
    if operator == "equals":
        return value == expected
    if operator == "contains":
        return _contains(value, expected)
    if operator == "contains_any":
        if not isinstance(expected, (list, tuple)):
            raise TypeError("contains_any expects a list or tuple")
        return any(_contains(value, item) for item in expected)
    if operator == "exists":
        return (value is not None) is bool(expected)
    raise ValueError(f"unsupported criterion operator: {operator}")


def _field_value(email: NormalizedEmail, path: str) -> Any:
    value: Any = email
    for part in path.split("."):
        if isinstance(value, Mapping):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            return None
    return value


def _contains(value: Any, expected: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return str(expected).lower() in value.lower()
    if isinstance(value, (tuple, list, set, frozenset)):
        return str(expected).lower() in {str(item).lower() for item in value}
    return str(expected).lower() in str(value).lower()
