"""
Agent Trust Layer — Who to trust, which protocols are safe.

Core insight from Bankr exploit:
The agent processed external input because it had no concept of
"who sent this" or "is this a trusted protocol."

This module gives agents:
1. Cryptographic identity verification
2. Protocol trust registry
3. Reputation tracking
4. Trust delegation (who vouches for whom)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import hashlib
import json


class TrustLevel(Enum):
    UNTRUSTED = 0      # Unknown entity — no interaction history
    OBSERVED = 1       # Seen but not verified
    VERIFIED = 2       # Cryptographic identity confirmed
    TRUSTED = 3        # Positive interaction history
    GUARANTEED = 4     # Vouched for by multiple trusted parties


class ProtocolStatus(Enum):
    UNKNOWN = "unknown"
    AUDITED = "audited"
    VERIFIED = "verified"       # Code verified by trusted auditor
    DEPRECATED = "deprecated"   # Known issues — avoid
    BANNED = "banned"           # Confirmed malicious


@dataclass
class AgentIdentity:
    """Cryptographic identity for an agent."""
    address: str                # Wallet address (primary key)
    name: str                   # Human-readable name
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None  # Who verified this agent
    public_key: Optional[str] = None   # For signature verification
    reputation_score: float = 0.0       # -1.0 (bad) to 1.0 (excellent)
    interaction_count: int = 0
    successful_interactions: int = 0
    failed_interactions: int = 0
    last_interaction: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)  # e.g., ["trader", "validator"]
    vouched_by: list[str] = field(default_factory=list)  # Addresses that trust this agent


@dataclass
class ProtocolEntry:
    """A registered protocol in the trust registry."""
    name: str
    chain: str
    status: ProtocolStatus
    contracts: list[str] = field(default_factory=list)  # Verified contract addresses
    audited_by: Optional[str] = None
    audit_date: Optional[datetime] = None
    risk_score: float = 0.0   # 0.0 (safe) to 1.0 (dangerous)
    notes: str = ""
    added_by: Optional[str] = None


@dataclass
class TrustDecision:
    """Result of a trust check."""
    allowed: bool
    entity: str
    trust_level: TrustLevel
    reason: str
    requires_approval: bool = False  # If trust is borderline


class TrustRegistry:
    """
    Central trust registry for agents and protocols.
    
    Agents query this before:
    - Executing transfers
    - Interacting with protocols
    - Processing external commands
    """
    
    def __init__(self):
        self.agents: dict[str, AgentIdentity] = {}
        self.protocols: dict[str, ProtocolEntry] = {}
        self.trust_vouches: dict[str, set[str]] = {}  # who vouches for whom
    
       # ── Agent Operations ────────────────────────────────────────
    
    def register_agent(self, identity: AgentIdentity) -> None:
        """Register or update an agent identity."""
        self.agents[identity.address.lower()] = identity
    
    def get_agent(self, address: str) -> AgentIdentity | None:
        """Look up an agent by address."""
        return self.agents.get(address.lower())
    
    def verify_agent(self, address: str, verifier: str) -> None:
        """Mark an agent as cryptographically verified."""
        agent = self.get_agent(address)
        if agent:
            agent.trust_level = TrustLevel.VERIFIED
            agent.verified_at = datetime.now(timezone.utc)
            agent.verified_by = verifier
    
    def vouch_for(self, voucher_address: str, target_address: str) -> dict:
        """One trusted agent vouches for another. Builds trust network."""
        target = self.get_agent(target_address)
        if not target:
            return {"error": "Target agent not registered"}
        
        if voucher_address.lower() not in target.vouched_by:
            target.vouched_by.append(voucher_address.lower())
        
        # Upgrade trust based on vouches
        if len(target.vouched_by) >= 3 and target.trust_level.value < TrustLevel.TRUSTED.value:
            target.trust_level = TrustLevel.TRUSTED
        elif len(target.vouched_by) >= 5 and target.trust_level.value < TrustLevel.GUARANTEED.value:
            target.trust_level = TrustLevel.GUARANTEED
        
        return {
            "status": "vouched",
            "target": target_address,
            "vouches": len(target.vouched_by),
            "new_trust_level": target.trust_level.name,
        }
    
    def record_interaction(self, address: str, success: bool) -> None:
        """Record an interaction outcome. Builds reputation."""
        agent = self.get_agent(address)
        if not agent:
            return
        
        agent.interaction_count += 1
        agent.last_interaction = datetime.now(timezone.utc)
        
        if success:
            agent.successful_interactions += 1
            # Positive reputation boost (diminishing returns)
            boost = 0.1 / (1 + agent.interaction_count * 0.1)
            agent.reputation_score = min(1.0, agent.reputation_score + boost)
        else:
            agent.failed_interactions += 1
            # Negative reputation hit (harsher than positive)
            agent.reputation_score = max(-1.0, agent.reputation_score - 0.2)
            
            # Demote trust on repeated failures
            if agent.failed_interactions >= 3:
                agent.trust_level = TrustLevel.OBSERVED
    
    # ── Protocol Operations ──────────────────────────────────────
    
    def register_protocol(self, protocol: ProtocolEntry) -> None:
        """Register a protocol in the trust registry."""
        key = f"{protocol.chain}:{protocol.name}".lower()
        self.protocols[key] = protocol
    
    def get_protocol(self, chain: str, name: str) -> ProtocolEntry | None:
        """Look up a protocol."""
        return self.protocols.get(f"{chain}:{name}".lower())
    
    def is_protocol_safe(self, chain: str, name: str) -> TrustDecision:
        """Check if a protocol is safe to interact with."""
        protocol = self.get_protocol(chain, name)
        
        if not protocol:
            return TrustDecision(
                allowed=False,
                entity=f"{chain}:{name}",
                trust_level=TrustLevel.UNTRUSTED,
                reason="Protocol not in registry — unknown entity",
                requires_approval=True,
            )
        
        if protocol.status == ProtocolStatus.BANNED:
            return TrustDecision(
                allowed=False,
                entity=f"{chain}:{name}",
                trust_level=TrustLevel.UNTRUSTED,
                reason=f"BANNED: {protocol.notes}",
            )
        
        if protocol.status == ProtocolStatus.DEPRECATED:
            return TrustDecision(
                allowed=False,
                entity=f"{chain}:{name}",
                trust_level=TrustLevel.OBSERVED,
                reason=f"DEPRECATED: {protocol.notes}",
                requires_approval=True,
            )
        
        if protocol.status == ProtocolStatus.VERIFIED:
            return TrustDecision(
                allowed=True,
                entity=f"{chain}:{name}",
                trust_level=TrustLevel.VERIFIED,
                reason=f"Audited by {protocol.audited_by}, risk score: {protocol.risk_score}",
            )
        
        if protocol.status == ProtocolStatus.AUDITED:
            return TrustDecision(
                allowed=True,
                entity=f"{chain}:{name}",
                trust_level=TrustLevel.TRUSTED,
                reason=f"Code verified, risk score: {protocol.risk_score}",
            )
        
        # Unknown status
        return TrustDecision(
            allowed=False,
            entity=f"{chain}:{name}",
            trust_level=TrustLevel.OBSERVED,
            reason="Protocol exists but unverified status",
            requires_approval=True,
        )
    
    def check_contract(self, chain: str, protocol_name: str, contract_address: str) -> TrustDecision:
        """Check if a specific contract address belongs to a verified protocol."""
        protocol = self.get_protocol(chain, protocol_name)
        
        if not protocol:
            return TrustDecision(
                allowed=False,
                entity=contract_address,
                trust_level=TrustLevel.UNTRUSTED,
                reason="Protocol not registered",
                requires_approval=True,
            )
        
        verified = [c.lower() for c in protocol.contracts]
        if contract_address.lower() in verified:
            return TrustDecision(
                allowed=True,
                entity=contract_address,
                trust_level=TrustLevel.VERIFIED,
                reason=f"Verified contract for {protocol_name}",
            )
        
        return TrustDecision(
            allowed=False,
            entity=contract_address,
            trust_level=TrustLevel.OBSERVED,
            reason=f"Contract not in verified list for {protocol_name}",
            requires_approval=True,
        )
    
    # ── Composite Trust Check ────────────────────────────────────
    
    def trust_check(self, sender: str, protocol: str, contract: str = "") -> dict:
        """
        Full trust check before any action.
        
        Returns:
            - Is the sender trusted?
            - Is the protocol safe?
            - Is the contract verified?
            - Overall recommendation: proceed, approve, or block
        """
        # Sender check
        sender_agent = self.get_agent(sender)
        sender_trust = sender_agent.trust_level if sender_agent else TrustLevel.UNTRUSTED
        
        # Protocol check
        chain, name = protocol.split(":", 1) if ":" in protocol else ("unknown", protocol)
        protocol_decision = self.is_protocol_safe(chain, name)
        
        # Contract check
        contract_decision = None
        if contract:
            contract_decision = self.check_contract(chain, name, contract)
        
        # Overall decision
        if sender_trust == TrustLevel.UNTRUSTED and not protocol_decision.allowed:
            return {
                "decision": "block",
                "reason": "Unknown sender AND untrusted protocol",
                "sender_trust": sender_trust.name,
                "protocol_allowed": protocol_decision.allowed,
                "contract_allowed": contract_decision.allowed if contract_decision else None,
            }
        
        if sender_trust.value < TrustLevel.VERIFIED.value or not protocol_decision.allowed:
            return {
                "decision": "approve",
                "reason": "Low trust sender or unverified protocol — human approval needed",
                "sender_trust": sender_trust.name,
                "protocol_allowed": protocol_decision.allowed,
                "contract_allowed": contract_decision.allowed if contract_decision else None,
            }
        
        return {
            "decision": "proceed",
            "reason": "All trust checks passed",
            "sender_trust": sender_trust.name,
            "protocol_allowed": protocol_decision.allowed,
            "contract_allowed": contract_decision.allowed if contract_decision else None,
        }
    
    # ── Export/Import ────────────────────────────────────────────
    
    def export_registry(self) -> str:
        """Export trust registry as JSON for persistence."""
        data = {
            "agents": {
                addr: {
                    "name": a.name,
                    "trust_level": a.trust_level.value,
                    "reputation_score": a.reputation_score,
                    "interaction_count": a.interaction_count,
                    "successful_interactions": a.successful_interactions,
                    "failed_interactions": a.failed_interactions,
                    "tags": a.tags,
                    "vouched_by": a.vouched_by,
                }
                for addr, a in self.agents.items()
            },
            "protocols": {
                key: {
                    "name": p.name,
                    "chain": p.chain,
                    "status": p.status.value,
                    "risk_score": p.risk_score,
                    "contracts": p.contracts,
                }
                for key, p in self.protocols.items()
            },
        }
        return json.dumps(data, indent=2)
