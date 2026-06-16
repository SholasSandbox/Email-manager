"""JSON policy loader for provider-neutral email rules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


SUPPORTED_ACTIONS = frozenset({"archive", "delete", "trash", "label", "mark_read", "flag", "skip"})


@dataclass(frozen=True)
class PolicyAction:
    """A single action a rule can request."""

    type: str
    params: Mapping[str, Any] = MappingProxyType({})

    def __post_init__(self) -> None:
        action_type = str(self.type).strip().lower()
        if action_type not in SUPPORTED_ACTIONS:
            raise ValueError(f"unsupported policy action: {self.type}")
        if not isinstance(self.params, Mapping):
            raise TypeError("policy action params must be a mapping")
        object.__setattr__(self, "type", action_type)
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))


@dataclass(frozen=True)
class PolicyRule:
    """A named policy rule with criteria and actions."""

    name: str
    criteria: Mapping[str, Any]
    actions: tuple[PolicyAction, ...]
    description: str = ""

    def __post_init__(self) -> None:
        name = self.name.strip()
        if not name:
            raise ValueError("policy rule name is required")
        if not isinstance(self.criteria, Mapping):
            raise TypeError("policy rule criteria must be a mapping")
        if not self.actions:
            raise ValueError(f"policy rule '{name}' must define at least one action")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "criteria", MappingProxyType(dict(self.criteria)))
        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(self, "description", self.description.strip())


@dataclass(frozen=True)
class EmailPolicy:
    """A validated email policy document."""

    name: str
    version: str
    rules: tuple[PolicyRule, ...]
    retention_thresholds: Mapping[str, Any] = MappingProxyType({})
    mode: str = "dry_run"
    destructive_confidence_threshold: Any = None

    def __post_init__(self) -> None:
        name = self.name.strip()
        version = self.version.strip()
        mode = str(self.mode or "dry_run").strip() or "dry_run"
        if not isinstance(self.retention_thresholds, Mapping):
            raise TypeError("policy retention_thresholds must be a mapping")
        if not name:
            raise ValueError("policy name is required")
        if not version:
            raise ValueError("policy version is required")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "mode", mode)
        object.__setattr__(
            self,
            "retention_thresholds",
            MappingProxyType(dict(self.retention_thresholds)),
        )


def load_policy(path: str | Path) -> EmailPolicy:
    """Load and validate an email policy from a JSON file."""

    with Path(path).open("r", encoding="utf-8") as policy_file:
        data = json.load(policy_file)
    return parse_policy(data)


def parse_policy(data: Mapping[str, Any]) -> EmailPolicy:
    """Validate a policy mapping and return an immutable policy object."""

    if not isinstance(data, Mapping):
        raise TypeError("policy document must be a mapping")

    rules_data = data.get("rules", ())
    if not isinstance(rules_data, list):
        raise TypeError("policy rules must be a list")

    return EmailPolicy(
        name=str(data.get("name", "")),
        version=str(data.get("version", "")),
        retention_thresholds=data.get("retention_thresholds", {}),
        mode=str(data.get("mode", "dry_run")),
        destructive_confidence_threshold=data.get("destructive_confidence_threshold"),
        rules=tuple(_parse_rule(rule) for rule in rules_data),
    )


def _parse_rule(data: Mapping[str, Any]) -> PolicyRule:
    if not isinstance(data, Mapping):
        raise TypeError("policy rule must be a mapping")

    actions_data = data.get("actions", ())
    if not isinstance(actions_data, list):
        raise TypeError("policy rule actions must be a list")

    return PolicyRule(
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
        criteria=data.get("criteria", {}),
        actions=tuple(_parse_action(action) for action in actions_data),
    )


def _parse_action(data: Mapping[str, Any]) -> PolicyAction:
    if not isinstance(data, Mapping):
        raise TypeError("policy action must be a mapping")
    return PolicyAction(
        type=str(data.get("type", "")),
        params=data.get("params", {}),
    )
