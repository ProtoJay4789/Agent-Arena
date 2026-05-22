"""TradeTagger: Enriches raw trade data with context tags before storing."""
import json
from datetime import datetime
from brain.store import MemoryStore


class TradeTagger:
    def __init__(self, store: MemoryStore):
        self.store = store

    def tag_trade(self, trade: dict) -> dict:
        """Tag a raw trade with context.

        Input dict:
            {action, token, amount, price, timestamp, player_id,
             reasoning?, price_1h_ago?}
        """
        tagged = dict(trade)
        player_id = trade.get("player_id", "default")
        amount = trade.get("amount", 0)
        action = trade.get("action", "")
        reasoning = trade.get("reasoning", "")
        price = trade.get("price", 0)
        price_1h_ago = trade.get("price_1h_ago", price)

        # --- market_conditions ------------------------------------------------
        if price_1h_ago and price_1h_ago != 0:
            pct_change = abs((price - price_1h_ago) / price_1h_ago) * 100
        else:
            pct_change = 0

        if pct_change > 5:
            market_conditions = "volatile"
        elif pct_change > 2:
            market_conditions = "stable"
        else:
            market_conditions = "calm"

        # --- emotional_state ---------------------------------------------------
        avg_amount = self._average_trade_amount(player_id)

        if avg_amount and amount > avg_amount * 2:
            emotional_state = "fomo"
        elif action == "sell" and self._recent_losses(player_id):
            emotional_state = "panic"
        elif reasoning and avg_amount and amount < avg_amount:
            emotional_state = "confident"
        else:
            emotional_state = "neutral"

        tags = {
            "market_conditions": market_conditions,
            "emotional_state": emotional_state,
            "reasoning": reasoning,
            "outcome": None,
        }
        tagged["tags"] = tags
        return tagged

    def resolve_trade(self, trade_id: int, outcome: dict) -> dict:
        """Update a stored trade with outcome data.

        outcome: {pnl: float, duration_minutes: int, success: bool}
        """
        memory = self.store.get_memory(trade_id)
        if memory is None:
            raise ValueError(f"Trade {trade_id} not found")

        tags = memory.get("tags", {})
        tags["outcome"] = outcome
        metadata = memory.get("metadata", {})
        metadata["pnl"] = outcome.get("pnl", 0)
        metadata["duration_minutes"] = outcome.get("duration_minutes", 0)
        metadata["success"] = outcome.get("success", False)

        # Re-store by updating — MemoryStore has no update, so we re-add
        # with the same content and rely on the original memory being
        # sufficient.  For the MVP we just mutate the DB row directly.
        self.store._conn.execute(
            "UPDATE memories SET tags = ?, metadata = ? WHERE id = ?",
            (json.dumps(tags), json.dumps(metadata), trade_id),
        )
        self.store._conn.commit()

        return self.store.get_memory(trade_id)

    def store_trade(self, tagged_trade: dict) -> int:
        """Store a tagged trade as a memory in the brain. Returns memory ID."""
        content = json.dumps({
            "action": tagged_trade.get("action"),
            "token": tagged_trade.get("token"),
            "amount": tagged_trade.get("amount"),
            "price": tagged_trade.get("price"),
            "timestamp": tagged_trade.get("timestamp"),
        })
        player_id = tagged_trade.get("player_id", "default")
        tags = tagged_trade.get("tags", {})
        metadata = {
            "reasoning": tagged_trade.get("reasoning", ""),
            "original_trade": tagged_trade,
        }
        return self.store.add_memory(
            content=content,
            layer="short_term",
            tags=tags,
            metadata=metadata,
            player_id=player_id,
        )

    def get_trade_history(self, player_id: str = "default", limit: int = 50) -> list:
        """Get all trade memories for a player."""
        return self.store.query_by_layer("short_term", player_id, limit)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _average_trade_amount(self, player_id: str) -> float:
        """Compute average trade amount from existing trade memories."""
        trades = self.store.query_by_layer("short_term", player_id, limit=100)
        amounts = []
        for t in trades:
            try:
                content = json.loads(t["content"]) if isinstance(t["content"], str) else t["content"]
                amounts.append(content.get("amount", 0))
            except (json.JSONDecodeError, AttributeError):
                continue
        return sum(amounts) / len(amounts) if amounts else 0

    def _recent_losses(self, player_id: str) -> bool:
        """Check if recent trades had losses."""
        trades = self.store.query_by_layer("short_term", player_id, limit=5)
        for t in trades:
            outcome = t.get("tags", {}).get("outcome")
            if outcome and isinstance(outcome, dict) and outcome.get("success") is False:
                return True
        return False
