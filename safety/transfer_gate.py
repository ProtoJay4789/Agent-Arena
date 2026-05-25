"""
Transfer Gate — Human-in-the-loop for all agent transfers.

Pattern: Agent proposes → Risk check → Human confirms → Execute

Prevents Bankr-style exploits where AI processes external input as commands.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import json


class RiskLevel(Enum):
    LOW = "low"           # < $100, to allowlisted address
    MEDIUM = "medium"     # $100-$1000 or new address
    HIGH = "high"         # > $1000 or unusual pattern
    CRITICAL = "critical" # Multiple transfers in short window


@dataclass
class TransferRequest:
    """A proposed transfer that needs human approval."""
    id: str
    from_agent: str
    to_address: str
    token: str
    amount: float
    amount_usd: float
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    risk_level: RiskLevel = RiskLevel.LOW
    approved: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected: bool = False
    reject_reason: Optional[str] = None


class TransferGate:
    """
    Enforces human approval for all transfers.
    
    No transfer executes without explicit user confirmation.
    This is the primary defense against prompt injection attacks.
    """
    
    def __init__(self, allowlist: list[str] | None = None, daily_limit_usd: float = 10000):
        self.allowlist = set(a.lower() for a in (allowlist or []))
        self.daily_limit_usd = daily_limit_usd
        self.pending: dict[str, TransferRequest] = {}
        self.executed_today: float = 0
        self.today_date: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def evaluate(self, request: TransferRequest) -> TransferRequest:
        """Assess risk level of a transfer request."""
        # Reset daily counter if new day
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self.today_date:
            self.executed_today = 0
            self.today_date = today
        
        # Check daily limit
        if self.executed_today + request.amount_usd > self.daily_limit_usd:
            request.risk_level = RiskLevel.CRITICAL
            return request
        
        # Risk scoring
        if request.amount_usd > 1000:
            request.risk_level = RiskLevel.HIGH
        elif request.amount_usd > 100 or request.to_address.lower() not in self.allowlist:
            request.risk_level = RiskLevel.MEDIUM
        else:
            request.risk_level = RiskLevel.LOW
        
        return request
    
    def request_approval(self, request: TransferRequest) -> dict:
        """Submit a transfer for human approval. Returns approval status."""
        request = self.evaluate(request)
        self.pending[request.id] = request
        
        return {
            "status": "pending_approval",
            "request_id": request.id,
            "risk_level": request.risk_level.value,
            "amount_usd": request.amount_usd,
            "to_address": request.to_address,
            "requires_confirmation": request.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL),
            "message": self._approval_message(request),
        }
    
    def approve(self, request_id: str, approver: str = "user") -> dict:
        """Human approves the transfer."""
        if request_id not in self.pending:
            return {"error": "Request not found"}
        
        request = self.pending[request_id]
        request.approved = True
        request.approved_by = approver
        request.approved_at = datetime.now(timezone.utc)
        
        # Update daily counter
        self.executed_today += request.amount_usd
        
        # Move to executed
        del self.pending[request_id]
        
        return {
            "status": "approved",
            "request_id": request_id,
            "executed": True,
            "amount_usd": request.amount_usd,
        }
    
    def reject(self, request_id: str, reason: str = "User rejected") -> dict:
        """Human rejects the transfer."""
        if request_id not in self.pending:
            return {"error": "Request not found"}
        
        request = self.pending[request_id]
        request.rejected = True
        request.reject_reason = reason
        
        del self.pending[request_id]
        
        return {
            "status": "rejected",
            "request_id": request_id,
            "reason": reason,
        }
    
    def _approval_message(self, request: TransferRequest) -> str:
        """Generate human-readable approval message."""
        risk_emoji = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🔴",
            RiskLevel.CRITICAL: "🚨",
        }
        
        emoji = risk_emoji.get(request.risk_level, "⚪")
        
        return (
            f"{emoji} Transfer Request\n"
            f"Amount: ${request.amount_usd:.2f} ({request.amount} {request.token})\n"
            f"To: {request.to_address[:8]}...{request.to_address[-4:]}\n"
            f"Reason: {request.reason}\n"
            f"Risk: {request.risk_level.value.upper()}\n"
            f"\nReply 'approve {request.id}' to confirm."
        )
