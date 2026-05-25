"""
Circuit Breaker — Rate limiting and emergency stops.

Prevents:
- Rapid-fire transfer draining (Bot draining wallet in seconds)
- Unusual activity patterns
- Runaway agent behavior
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Circuit tripped — all transfers blocked
    HALF_OPEN = "half_open" # Testing if恢复正常


@dataclass
class CircuitBreaker:
    """Rate limiter and emergency stop for agent transfers."""
    
    max_transfers_per_hour: int = 5
    max_transfers_per_day: int = 20
    max_usd_per_hour: float = 5000
    max_usd_per_day: float = 50000
    cooldown_minutes: int = 30
    
    state: CircuitState = CircuitState.CLOSED
    transfers_this_hour: int = 0
    transfers_today: int = 0
    usd_this_hour: float = 0
    usd_today: float = 0
    last_transfer_time: datetime | None = None
    circuit_opened_at: datetime | None = None
    consecutive_rejections: int = 0
    
    # Tracking
    transfer_log: list[dict] = field(default_factory=list)
    
    def check(self, amount_usd: float) -> dict:
        """Check if a transfer is allowed. Returns allowed + reason."""
        
        # If circuit is open, block everything
        if self.state == CircuitState.OPEN:
            if self.circuit_opened_at:
                elapsed = (datetime.now(timezone.utc) - self.circuit_opened_at).total_seconds() / 60
                if elapsed >= self.cooldown_minutes:
                    self.state = CircuitState.HALF_OPEN
                    return {"allowed": True, "state": "half_open", "reason": "Cooldown elapsed, testing"}
            return {"allowed": False, "state": "open", "reason": "Circuit breaker active"}
        
        now = datetime.now(timezone.utc)
        
        # Reset hourly counter
        if self.last_transfer_time:
            hours_since = (now - self.last_transfer_time).total_seconds() / 3600
            if hours_since >= 1:
                self.transfers_this_hour = 0
                self.usd_this_hour = 0
        
        # Check hourly limits
        if self.transfers_this_hour >= self.max_transfers_per_hour:
            self._trip_circuit("Hourly transfer limit reached")
            return {"allowed": False, "state": "open", "reason": "Hourly limit reached"}
        
        if self.usd_this_hour + amount_usd > self.max_usd_per_hour:
            self._trip_circuit("Hourly USD limit reached")
            return {"allowed": False, "state": "open", "reason": "Hourly USD limit reached"}
        
        # Check daily limits
        if self.transfers_today >= self.max_transfers_per_day:
            return {"allowed": False, "state": "open", "reason": "Daily limit reached"}
        
        if self.usd_today + amount_usd > self.max_usd_per_day:
            return {"allowed": False, "state": "open", "reason": "Daily USD limit reached"}
        
        # Check rapid-fire (3+ transfers in 1 minute)
        if len(self.transfer_log) >= 3:
            last_3 = self.transfer_log[-3:]
            if last_3:
                time_span = (now - last_3[0]["time"]).total_seconds()
                if time_span < 60:
                    self._trip_circuit("Rapid-fire detected")
                    return {"allowed": False, "state": "open", "reason": "Rapid-fire detected"}
        
        return {"allowed": True, "state": self.state.value, "reason": "OK"}
    
    def record_transfer(self, amount_usd: float) -> None:
        """Record a completed transfer."""
        now = datetime.now(timezone.utc)
        self.transfers_this_hour += 1
        self.transfers_today += 1
        self.usd_this_hour += amount_usd
        self.usd_today += amount_usd
        self.last_transfer_time = now
        self.consecutive_rejections = 0
        self.transfer_log.append({"time": now, "amount_usd": amount_usd})
        
        # Keep only last 100 entries
        if len(self.transfer_log) > 100:
            self.transfer_log = self.transfer_log[-100:]
    
    def record_rejection(self) -> None:
        """Record a rejected transfer attempt."""
        self.consecutive_rejections += 1
        if self.consecutive_rejections >= 3:
            self._trip_circuit("3 consecutive rejections")
    
    def emergency_stop(self) -> dict:
        """Manual emergency stop. Blocks all transfers until reset."""
        self._trip_circuit("Manual emergency stop")
        return {"status": "stopped", "message": "All transfers blocked. Reset required."}
    
    def reset(self) -> dict:
        """Reset circuit breaker. Requires manual action."""
        self.state = CircuitState.CLOSED
        self.circuit_opened_at = None
        self.consecutive_rejections = 0
        return {"status": "reset", "message": "Circuit breaker reset. Normal operation resumed."}
    
    def _trip_circuit(self, reason: str) -> None:
        """Trip the circuit breaker."""
        self.state = CircuitState.OPEN
        self.circuit_opened_at = datetime.now(timezone.utc)
        self.transfer_log.append({
            "time": datetime.now(timezone.utc),
            "event": "circuit_tripped",
            "reason": reason,
        })
    
    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "state": self.state.value,
            "transfers_this_hour": self.transfers_this_hour,
            "transfers_today": self.transfers_today,
            "usd_this_hour": self.usd_this_hour,
            "usd_today": self.usd_today,
            "consecutive_rejections": self.consecutive_rejections,
            "limits": {
                "max_transfers_per_hour": self.max_transfers_per_hour,
                "max_transfers_per_day": self.max_transfers_per_day,
                "max_usd_per_hour": self.max_usd_per_hour,
                "max_usd_per_day": self.max_usd_per_day,
            },
        }
