"""
Governance Engine — OWASP ASI rule evaluation for DeFi agents.

Loads rules from YAML policy files and evaluates agent actions against them.
Each rule has a condition (field/operator/value), an action (allow/deny/audit/require_approval),
and a priority. Rules are evaluated in priority order; first matching rule wins.

Pattern: Agent proposes → Governance checks → Allow/Deny/Audit → Execute
"""

import re
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import yaml


class GovernanceAction(Enum):
    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"  # Alias for deny, but semantically stronger


class Operator(Enum):
    EQ = "eq"
    MATCHES = "matches"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    CONTAINS = "contains"


@dataclass
class RuleCondition:
    field: str
    operator: str
    value: Any


@dataclass
class GovernanceRule:
    name: str
    condition: RuleCondition
    action: str
    priority: int = 50
    message: str = ""

    def matches(self, context: dict) -> bool:
        """Check if this rule matches the given context."""
        field_value = context.get(self.condition.field)
        if field_value is None:
            return False

        op = self.condition.operator
        expected = self.condition.value

        if op == "eq":
            return str(field_value).lower() == str(expected).lower()
        elif op == "matches":
            # String regex match
            if not isinstance(field_value, str):
                field_value = str(field_value)
            return bool(re.search(expected, field_value, re.IGNORECASE))
        elif op == "gt":
            try:
                return float(field_value) > float(expected)
            except (ValueError, TypeError):
                return False
        elif op == "lt":
            try:
                return float(field_value) < float(expected)
            except (ValueError, TypeError):
                return False
        elif op == "gte":
            try:
                return float(field_value) >= float(expected)
            except (ValueError, TypeError):
                return False
        elif op == "lte":
            try:
                return float(field_value) <= float(expected)
            except (ValueError, TypeError):
                return False
        elif op == "contains":
            return str(expected).lower() in str(field_value).lower()
        return False


@dataclass
class GovernanceResult:
    allowed: bool
    action: str  # The governance action taken
    rule_name: Optional[str]  # Which rule matched
    message: str  # Human-readable explanation
    requires_approval: bool = False
    audit_only: bool = False
    matched_rules: list[dict] = field(default_factory=list)


class GovernanceEngine:
    """
    Rule-based governance engine for DeFi agent operations.

    Loads rules from YAML policy files and evaluates actions against them.
    Supports deny-by-default policy with priority-based rule matching.

    Usage:
        engine = GovernanceEngine()
        engine.load_policies("safety/policies/defi-governance.yaml")
        result = engine.evaluate(action="transfer_usdc", output="send 100 USDC")
        if not result.allowed:
            print(f"Blocked: {result.message}")
    """

    DEFAULT_POLICIES_DIR = os.path.join(os.path.dirname(__file__), "policies")

    def __init__(self, deny_by_default: bool = True):
        self.rules: list[GovernanceRule] = []
        self.deny_by_default = deny_by_default
        self.defaults: dict = {
            "action": "deny",
            "max_tokens": 6000,
            "max_tool_calls": 20,
            "confidence_threshold": 0.95,
        }
        self.metadata: dict = {}
        self._compiled_cache: dict[str, list] = {}

    def load_policies(self, filepath: str) -> dict:
        """
        Load governance rules from a YAML file.

        Returns a summary dict with rule count and loaded policies.
        """
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            return {"rules_loaded": 0, "policies": []}

        self.metadata = {
            "version": data.get("version", "unknown"),
            "name": data.get("name", "unknown"),
            "description": data.get("description", ""),
        }

        if "defaults" in data:
            self.defaults.update(data["defaults"])

        rules_loaded = 0
        for rule_data in data.get("rules", []):
            condition_data = rule_data.get("condition", {})
            condition = RuleCondition(
                field=condition_data.get("field", ""),
                operator=condition_data.get("operator", "eq"),
                value=condition_data.get("value", ""),
            )
            rule = GovernanceRule(
                name=rule_data.get("name", "unnamed"),
                condition=condition,
                action=rule_data.get("action", "deny"),
                priority=rule_data.get("priority", 50),
                message=rule_data.get("message", ""),
            )
            self.rules.append(rule)
            rules_loaded += 1

        # Sort rules by priority (highest first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

        return {
            "rules_loaded": rules_loaded,
            "policies": [self.metadata.get("name", "unknown")],
        }

    def load_default_policies(self) -> dict:
        """Load the built-in defi-governance.yaml from the policies directory."""
        default_path = os.path.join(self.DEFAULT_POLICIES_DIR, "defi-governance.yaml")
        if os.path.exists(default_path):
            return self.load_policies(default_path)
        return {"rules_loaded": 0, "policies": []}

    def add_rule(self, rule: GovernanceRule) -> None:
        """Add a custom rule at runtime."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, action: str = "", output: str = "", **kwargs) -> GovernanceResult:
        """
        Evaluate an action against all governance rules.

        Context fields:
            - action: The action name (e.g., "transfer_usdc", "execute_code")
            - output: The text/output to check
            - Any additional keyword args become context fields

        Returns a GovernanceResult with allow/deny and rule reference.
        """
        context = {"action": action, "output": output}
        context.update(kwargs)

        matched_rules = []
        winning_action = self.defaults.get("action", "deny")
        winning_rule_name = None
        winning_message = "Default policy applied"

        for rule in self.rules:
            if rule.matches(context):
                matched_rules.append({
                    "name": rule.name,
                    "action": rule.action,
                    "priority": rule.priority,
                    "message": rule.message,
                })
                # First match wins (rules are sorted by priority)
                if winning_rule_name is None:
                    winning_action = rule.action
                    winning_rule_name = rule.name
                    winning_message = rule.message

        # Determine allowed status
        if winning_rule_name is None:
            # No rules matched — use deny_by_default flag
            allowed = not self.deny_by_default
            requires_approval = False
            audit_only = False
            winning_action = "allow" if allowed else "deny"
            winning_message = "No rules matched — default policy"
        elif winning_action == "allow":
            allowed = True
            requires_approval = False
            audit_only = False
        elif winning_action == "audit":
            allowed = True
            requires_approval = False
            audit_only = True
        elif winning_action == "require_approval":
            allowed = True
            requires_approval = True
            audit_only = False
        elif winning_action in ("deny", "block"):
            allowed = False
            requires_approval = False
            audit_only = False
        else:
            # Unknown action type — fall back to deny_by_default
            allowed = not self.deny_by_default
            requires_approval = False
            audit_only = False

        return GovernanceResult(
            allowed=allowed,
            action=winning_action,
            rule_name=winning_rule_name,
            message=winning_message,
            requires_approval=requires_approval,
            audit_only=audit_only,
            matched_rules=matched_rules,
        )

    def get_rules(self) -> list[dict]:
        """Return all loaded rules as dicts."""
        return [
            {
                "name": r.name,
                "action": r.action,
                "priority": r.priority,
                "message": r.message,
                "condition": {
                    "field": r.condition.field,
                    "operator": r.condition.operator,
                    "value": str(r.condition.value),
                },
            }
            for r in self.rules
        ]

    def get_status(self) -> dict:
        """Get engine status."""
        return {
            "rules_count": len(self.rules),
            "deny_by_default": self.deny_by_default,
            "metadata": self.metadata,
            "defaults": self.defaults,
        }
