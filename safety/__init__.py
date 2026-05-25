"""
AAE Safety Layer — Anti-Bankr-Exploit Protection

Prevents prompt injection attacks on AI trading agents.

Components:
- TransferGate: Human-in-the-loop for all transfers
- InputFirewall: Never trust external data as commands
- CircuitBreaker: Rate limiting and emergency stops

Pattern: Agent proposes → Risk check → Human confirms → Execute
"""

from .transfer_gate import TransferGate, TransferRequest, RiskLevel
from .input_firewall import InputFirewall, InputSource, ThreatLevel
from .circuit_breaker import CircuitBreaker, CircuitState
from .trust_registry import TrustRegistry, AgentIdentity, ProtocolEntry, TrustLevel, ProtocolStatus


class SafetyLayer:
    """
    Unified safety interface for Agent Arena.
    
    Usage:
        safety = SafetyLayer(allowlist=["0x..."])
        
        # Before any transfer
        result = safety.check_transfer(to="0x...", amount=100, token="USDC")
        if result["requires_approval"]:
            # Show approval UI, wait for user
            pass
        
        # Validate external input
        verdict = safety.validate_input(text, source=InputSource.NFT_METADATA)
        if verdict.blocked:
            return  # Don't process
        
        # Trust check — who is this agent?
        trust = safety.trust_check(sender="0xABC", protocol="solana:jupiter")
    """
    
    def __init__(
        self,
        allowlist: list[str] | None = None,
        daily_limit_usd: float = 10000,
        max_transfers_per_hour: int = 5,
    ):
        self.transfer_gate = TransferGate(allowlist=allowlist, daily_limit_usd=daily_limit_usd)
        self.input_firewall = InputFirewall()
        self.circuit_breaker = CircuitBreaker(max_transfers_per_hour=max_transfers_per_hour)
        self.trust_registry = TrustRegistry()
    
    def check_transfer(self, to: str, amount: float, token: str, reason: str = "") -> dict:
        """Full safety check for a transfer. Returns approval status."""
        # Circuit breaker check
        cb_result = self.circuit_breaker.check(amount)
        if not cb_result["allowed"]:
            return {
                "requires_approval": False,
                "blocked": True,
                "reason": cb_result["reason"],
                "circuit_state": cb_result["state"],
            }
        
        # Transfer gate check
        import uuid
        request = TransferRequest(
            id=str(uuid.uuid4())[:8],
            from_agent="arena",
            to_address=to,
            token=token,
            amount=amount,
            amount_usd=amount,  # Simplified — in production, convert to USD
            reason=reason,
        )
        
        gate_result = self.transfer_gate.request_approval(request)
        
        return {
            "requires_approval": True,
            "request_id": gate_result["request_id"],
            "risk_level": gate_result["risk_level"],
            "message": gate_result["message"],
            "circuit_state": cb_result["state"],
        }
    
    def approve_transfer(self, request_id: str) -> dict:
        """User approves a pending transfer."""
        result = self.transfer_gate.approve(request_id)
        if result.get("executed"):
            self.circuit_breaker.record_transfer(result.get("amount_usd", 0))
        return result
    
    def reject_transfer(self, request_id: str, reason: str = "") -> dict:
        """User rejects a pending transfer."""
        self.circuit_breaker.record_rejection()
        return self.transfer_gate.reject(request_id, reason)
    
    def validate_input(self, text: str, source: InputSource = InputSource.UNKNOWN) -> dict:
        """Validate external input. Returns safe/blocked status."""
        verdict = self.input_firewall.analyze(text, source)
        return {
            "safe": not verdict.blocked,
            "blocked": verdict.blocked,
            "threat_level": verdict.threat_level.value,
            "reason": verdict.reason,
        }
    
    def trust_check(self, sender: str, protocol: str, contract: str = "") -> dict:
        """Full trust check — is the sender trusted and protocol safe?"""
        return self.trust_registry.trust_check(sender, protocol, contract)
    
    def register_agent(self, address: str, name: str, tags: list[str] | None = None) -> None:
        """Register a known agent."""
        self.trust_registry.register_agent(AgentIdentity(
            address=address,
            name=name,
            tags=tags or [],
        ))
    
    def register_protocol(self, chain: str, name: str, contracts: list[str] | None = None) -> None:
        """Register a known safe protocol."""
        self.trust_registry.register_protocol(ProtocolEntry(
            name=name,
            chain=chain,
            status=ProtocolStatus.VERIFIED,
            contracts=contracts or [],
        ))
    
    def emergency_stop(self) -> dict:
        """Emergency stop — blocks all transfers."""
        return self.circuit_breaker.emergency_stop()
    
    def get_status(self) -> dict:
        """Get full safety system status."""
        return {
            "circuit_breaker": self.circuit_breaker.get_status(),
            "firewall_stats": self.input_firewall.get_stats(),
            "pending_approvals": len(self.transfer_gate.pending),
        }


__all__ = [
    "SafetyLayer",
    "TransferGate",
    "TransferRequest",
    "RiskLevel",
    "InputFirewall",
    "InputSource",
    "ThreatLevel",
    "CircuitBreaker",
    "CircuitState",
    "TrustRegistry",
    "AgentIdentity",
    "ProtocolEntry",
    "TrustLevel",
    "ProtocolStatus",
]
