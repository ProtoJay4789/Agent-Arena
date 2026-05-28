"""
Audit Trail — Tamper-evident hash chain for governance actions.

Every governance decision is recorded with:
1. Hash chain linking to previous entry (tamper-evident)
2. Agent/action/time metadata
3. Queryable by any field
4. Exportable to JSON

If any entry is modified, the chain breaks and verify_chain() detects it.
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


def _hash_entry(data: str, previous_hash: str) -> str:
    """Create SHA-256 hash linking to previous entry."""
    content = f"{previous_hash}:{data}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


GENESIS_HASH = "0" * 64  # Hash of the first "virtual" entry


@dataclass
class AuditEntry:
    """A single audit trail entry."""
    index: int
    timestamp: str
    agent: str
    action: str
    result: str  # allow/deny/audit/approval_required
    rule_name: Optional[str]
    message: str
    metadata: dict = field(default_factory=dict)
    previous_hash: str = GENESIS_HASH
    entry_hash: str = ""

    def to_json_str(self) -> str:
        """Serialize entry to JSON string for hashing."""
        data = {
            "index": self.index,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "action": self.action,
            "result": self.result,
            "rule_name": self.rule_name,
            "message": self.message,
            "metadata": self.metadata,
            "previous_hash": self.previous_hash,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":"))


class AuditTrail:
    """
    Tamper-evident audit trail using SHA-256 hash chain.

    Each entry includes the hash of the previous entry, creating a chain.
    Any modification to a past entry breaks the chain and is detectable.

    Usage:
        trail = AuditTrail()
        trail.add_entry(agent="bot_alpha", action="transfer_usdc", result="allow")
        trail.add_entry(agent="bot_alpha", action="swap_sol", result="deny",
                       rule_name="asi02-block-shell")
        print(trail.export_json())
        assert trail.verify_chain()  # Chain is intact
    """

    def __init__(self):
        self.entries: list[AuditEntry] = []
        self._last_hash: str = GENESIS_HASH

    def add_entry(
        self,
        agent: str,
        action: str,
        result: str,
        rule_name: Optional[str] = None,
        message: str = "",
        metadata: Optional[dict] = None,
    ) -> AuditEntry:
        """
        Add a new audit entry to the chain.

        Returns the created entry with computed hash.
        """
        entry = AuditEntry(
            index=len(self.entries),
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent=agent,
            action=action,
            result=result,
            rule_name=rule_name,
            message=message,
            metadata=metadata or {},
            previous_hash=self._last_hash,
        )

        # Compute hash
        entry.entry_hash = _hash_entry(entry.to_json_str(), entry.previous_hash)
        self._last_hash = entry.entry_hash

        self.entries.append(entry)
        return entry

    def query(
        self,
        agent: Optional[str] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        since: Optional[str] = None,
        before: Optional[str] = None,
    ) -> list[AuditEntry]:
        """
        Query audit entries by agent, action, result, or time range.

        Args:
            agent: Filter by agent name
            action: Filter by action type
            result: Filter by result (allow/deny/etc)
            since: ISO timestamp — entries after this time
            before: ISO timestamp — entries before this time
        """
        results = self.entries

        if agent is not None:
            results = [e for e in results if e.agent == agent]
        if action is not None:
            results = [e for e in results if e.action == action]
        if result is not None:
            results = [e for e in results if e.result == result]
        if since is not None:
            results = [e for e in results if e.timestamp >= since]
        if before is not None:
            results = [e for e in results if e.timestamp <= before]

        return results

    def verify_chain(self) -> bool:
        """
        Verify the integrity of the entire hash chain.

        Returns True if chain is intact, False if any entry was tampered with.
        """
        expected_prev = GENESIS_HASH

        for entry in self.entries:
            if entry.previous_hash != expected_prev:
                return False

            # Recompute hash
            computed_hash = _hash_entry(entry.to_json_str(), entry.previous_hash)
            if computed_hash != entry.entry_hash:
                return False

            expected_prev = entry.entry_hash

        return True

    def export_json(self, indent: int = 2) -> str:
        """Export the entire audit trail as JSON."""
        data = {
            "version": "1.0",
            "total_entries": len(self.entries),
            "chain_valid": self.verify_chain(),
            "chain_head": self._last_hash,
            "entries": [self._entry_to_dict(e) for e in self.entries],
        }
        return json.dumps(data, indent=indent)

    def _entry_to_dict(self, entry: AuditEntry) -> dict:
        """Convert entry to dict for JSON export."""
        return {
            "index": entry.index,
            "timestamp": entry.timestamp,
            "agent": entry.agent,
            "action": entry.action,
            "result": entry.result,
            "rule_name": entry.rule_name,
            "message": entry.message,
            "metadata": entry.metadata,
            "previous_hash": entry.previous_hash,
            "entry_hash": entry.entry_hash,
        }

    def get_stats(self) -> dict:
        """Get audit trail statistics."""
        agents = set()
        actions = set()
        results = {}
        for e in self.entries:
            agents.add(e.agent)
            actions.add(e.action)
            results[e.result] = results.get(e.result, 0) + 1

        return {
            "total_entries": len(self.entries),
            "unique_agents": len(agents),
            "unique_actions": len(actions),
            "results_breakdown": results,
            "chain_valid": self.verify_chain(),
        }
