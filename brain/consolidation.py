"""ConsolidationEngine: Memory lifecycle management for Echo Brain."""
from brain.store import MemoryStore


class ConsolidationEngine:
    def __init__(self, store: MemoryStore):
        self.store = store

    def decay_short_term(
        self, days_elapsed: float = 1.0, decay_rate: float = 0.1
    ) -> int:
        """Apply time-based decay to short-term memories.
        strength -= decay_rate * days_elapsed (min 0.0)
        Returns number of memories affected."""
        rows = self.store._conn.execute(
            "SELECT id, strength FROM memories WHERE layer = 'short_term'"
        ).fetchall()
        count = 0
        for row in rows:
            new_strength = max(0.0, row["strength"] - decay_rate * days_elapsed)
            self.store.update_strength(row["id"], new_strength)
            count += 1
        return count

    def promote_to_long_term(
        self, access_threshold: int = 3, strength_threshold: float = 0.5
    ) -> int:
        """Promote short-term memories that meet criteria to long-term.
        Criteria: access_count >= threshold OR strength >= threshold.
        Returns number promoted."""
        rows = self.store._conn.execute(
            """SELECT id FROM memories
               WHERE layer = 'short_term'
                 AND (access_count >= ? OR strength >= ?)""",
            (access_threshold, strength_threshold),
        ).fetchall()
        count = 0
        for row in rows:
            self.store._conn.execute(
                "UPDATE memories SET layer = 'long_term' WHERE id = ?",
                (row["id"],),
            )
            count += 1
        if count > 0:
            self.store._conn.commit()
        return count

    def remove_dead_memories(self) -> int:
        """Remove memories with strength <= 0. Returns number removed."""
        rows = self.store._conn.execute(
            "SELECT id FROM memories WHERE strength <= 0.0"
        ).fetchall()
        count = 0
        for row in rows:
            if self.store.delete_memory(row["id"]):
                count += 1
        return count

    def consolidate(self, days_elapsed: float = 1.0) -> dict:
        """Run full consolidation cycle.
        1. Decay short-term
        2. Promote qualifying memories
        3. Remove dead memories (strength <= 0)
        Returns: {decayed: int, promoted: int, removed: int}"""
        decayed = self.decay_short_term(days_elapsed=days_elapsed)
        promoted = self.promote_to_long_term()
        removed = self.remove_dead_memories()
        return {"decayed": decayed, "promoted": promoted, "removed": removed}

    def get_stats(self, player_id: str = "default") -> dict:
        """Get consolidation-relevant stats.
        Returns: {working: int, short_term: int, long_term: int,
                  avg_strength: dict, weakest_memories: list}"""
        layer_counts = {}
        for layer in ("working", "short_term", "long_term"):
            cur = self.store._conn.execute(
                "SELECT COUNT(*) as cnt FROM memories WHERE layer = ? AND player_id = ?",
                (layer, player_id),
            )
            layer_counts[layer] = cur.fetchone()["cnt"]

        avg_strength = {}
        for layer in ("working", "short_term", "long_term"):
            cur = self.store._conn.execute(
                "SELECT AVG(strength) as avg_s FROM memories WHERE layer = ? AND player_id = ?",
                (layer, player_id),
            )
            row = cur.fetchone()
            avg_strength[layer] = round(row["avg_s"], 4) if row["avg_s"] is not None else 0.0

        weakest = self.store._conn.execute(
            """SELECT id, content, layer, strength
               FROM memories WHERE player_id = ?
               ORDER BY strength ASC LIMIT 5""",
            (player_id,),
        ).fetchall()

        return {
            "working": layer_counts["working"],
            "short_term": layer_counts["short_term"],
            "long_term": layer_counts["long_term"],
            "avg_strength": avg_strength,
            "weakest_memories": [dict(r) for r in weakest],
        }
