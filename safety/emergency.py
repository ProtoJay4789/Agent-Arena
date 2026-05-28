"""
Emergency Stop — Global kill switch for all agent operations.

When activated, ALL agent operations are halted immediately.
This is the nuclear option — overrides everything else.

Three states:
1. INACTIVE — normal operation
2. ACTIVE — all operations halted
3. COOLDOWN — recently deactivated, restricted operations

Includes:
- Activate/deactivate
- Status check
- Reset capability
- Activation log with timestamps and reasons
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class EmergencyState(Enum):
    INACTIVE = "inactive"    # Normal operation
    ACTIVE = "active"        # All operations halted
    COOLDOWN = "cooldown"    # Recently deactivated, limited ops


@dataclass
class EmergencyEvent:
    """A recorded emergency event."""
    timestamp: str
    event_type: str  # activate, deactivate, reset
    reason: str
    operator: str = "system"


class EmergencyStop:
    """
    Global emergency stop for Agent Arena.

    When activated, ALL operations (transfers, trades, input processing)
    are halted until explicitly reset.

    Usage:
        emergency = EmergencyStop()
        emergency.activate("Security breach detected")
        assert emergency.is_active()
        # All operations should be blocked

        emergency.deactivate("Threat resolved", operator="admin")
        assert not emergency.is_active()
    """

    def __init__(self):
        self.state: EmergencyState = EmergencyState.INACTIVE
        self.events: list[EmergencyEvent] = []
        self.activated_at: Optional[datetime] = None
        self.deactivated_at: Optional[datetime] = None
        self.cooldown_seconds: int = 300  # 5 minutes cooldown
        self.activation_count: int = 0

    def activate(self, reason: str = "Manual emergency stop", operator: str = "system") -> dict:
        """
        Activate the emergency stop. Halts ALL operations.

        Returns activation status.
        """
        now = datetime.now(timezone.utc)

        if self.state == EmergencyState.ACTIVE:
            return {
                "status": "already_active",
                "message": "Emergency stop is already active",
                "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            }

        self.state = EmergencyState.ACTIVE
        self.activated_at = now
        self.activation_count += 1

        event = EmergencyEvent(
            timestamp=now.isoformat(),
            event_type="activate",
            reason=reason,
            operator=operator,
        )
        self.events.append(event)

        return {
            "status": "activated",
            "message": f"Emergency stop activated: {reason}",
            "activation_count": self.activation_count,
        }

    def deactivate(self, reason: str = "Threat resolved", operator: str = "system") -> dict:
        """
        Deactivate the emergency stop. Enters cooldown period.

        Returns deactivation status.
        """
        now = datetime.now(timezone.utc)

        if self.state == EmergencyState.INACTIVE:
            return {
                "status": "already_inactive",
                "message": "Emergency stop is not active",
            }

        self.state = EmergencyState.COOLDOWN
        self.deactivated_at = now

        event = EmergencyEvent(
            timestamp=now.isoformat(),
            event_type="deactivate",
            reason=reason,
            operator=operator,
        )
        self.events.append(event)

        return {
            "status": "deactivated",
            "message": f"Emergency stop deactivated: {reason}. Entering cooldown.",
            "cooldown_seconds": self.cooldown_seconds,
        }

    def reset(self, operator: str = "system") -> dict:
        """
        Full reset — clears all emergency state and cooldown.

        Returns reset status.
        """
        now = datetime.now(timezone.utc)

        event = EmergencyEvent(
            timestamp=now.isoformat(),
            event_type="reset",
            reason="Full reset requested",
            operator=operator,
        )
        self.events.append(event)

        self.state = EmergencyState.INACTIVE
        self.activated_at = None
        self.deactivated_at = None

        return {
            "status": "reset",
            "message": "Emergency stop fully reset. Normal operation resumed.",
        }

    def is_active(self) -> bool:
        """Check if emergency stop is currently active."""
        if self.state == EmergencyState.ACTIVE:
            return True

        # Check if still in cooldown
        if self.state == EmergencyState.COOLDOWN and self.deactivated_at:
            elapsed = (datetime.now(timezone.utc) - self.deactivated_at).total_seconds()
            if elapsed < self.cooldown_seconds:
                return True
            else:
                # Cooldown expired
                self.state = EmergencyState.INACTIVE
                return False

        return False

    def status(self) -> dict:
        """Get current emergency stop status."""
        now = datetime.now(timezone.utc)
        cooldown_remaining = 0

        if self.state == EmergencyState.COOLDOWN and self.deactivated_at:
            elapsed = (now - self.deactivated_at).total_seconds()
            cooldown_remaining = max(0, self.cooldown_seconds - elapsed)
            if cooldown_remaining <= 0:
                self.state = EmergencyState.INACTIVE

        return {
            "state": self.state.value,
            "is_active": self.is_active(),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "deactivated_at": self.deactivated_at.isoformat() if self.deactivated_at else None,
            "activation_count": self.activation_count,
            "cooldown_remaining": round(cooldown_remaining, 1),
            "total_events": len(self.events),
        }

    def get_events(self) -> list[dict]:
        """Get all emergency events."""
        return [
            {
                "timestamp": e.timestamp,
                "event_type": e.event_type,
                "reason": e.reason,
                "operator": e.operator,
            }
            for e in self.events
        ]

    def check_operation(self, operation_type: str = "any") -> dict:
        """
        Check if a specific operation is allowed under current emergency state.

        Returns allowed + reason.
        """
        if self.state == EmergencyState.ACTIVE:
            return {
                "allowed": False,
                "reason": "Emergency stop is active — all operations halted",
                "state": self.state.value,
            }

        if self.state == EmergencyState.COOLDOWN:
            return {
                "allowed": False,
                "reason": "Emergency cooldown period — restricted operations",
                "state": self.state.value,
            }

        return {
            "allowed": True,
            "reason": "No emergency stop active",
            "state": self.state.value,
        }
