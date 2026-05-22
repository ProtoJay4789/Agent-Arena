"""MemoryStore: Full CRUD interface for Echo Brain memories."""
import json
from typing import Optional

import numpy as np

from .schema import init_db


class MemoryStore:
    """High-level store for agent memories with cosine similarity search."""

    def __init__(self, db_path: str = "echo_brain.db"):
        """Initialize with SQLite database path."""
        self.db_path = db_path
        self._conn = init_db(db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _conn_factory(self) -> "sqlite3.Connection":
        """Return the live connection (already has row_factory=Row)."""
        return self._conn

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert a sqlite3.Row to a plain dict, deserializing JSON/BLOB."""
        d = dict(row)
        # Deserialize JSON fields
        for key in ("tags", "metadata"):
            if isinstance(d.get(key), str):
                d[key] = json.loads(d[key])
        # Deserialize embedding
        if d.get("embedding") is not None:
            d["embedding"] = np.frombuffer(d["embedding"], dtype=np.float64)
        return d

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_memory(
        self,
        content: str,
        layer: str,
        tags: dict = None,
        metadata: dict = None,
        embedding: "np.ndarray" = None,
        player_id: str = "default",
    ) -> int:
        """Add a memory, return its ID."""
        tags_json = json.dumps(tags or {})
        meta_json = json.dumps(metadata or {})
        emb_blob = embedding.tobytes() if embedding is not None else None
        cur = self._conn.execute(
            """INSERT INTO memories (layer, content, embedding, tags, metadata, player_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (layer, content, emb_blob, tags_json, meta_json, player_id),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_memory(self, memory_id: int) -> Optional[dict]:
        """Retrieve a single memory by ID. Updates accessed_at."""
        cur = self._conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        # Update access metadata
        self._conn.execute(
            """UPDATE memories
               SET accessed_at = CURRENT_TIMESTAMP,
                   access_count = access_count + 1
               WHERE id = ?""",
            (memory_id,),
        )
        self._conn.commit()
        return self._row_to_dict(row)

    def query_by_layer(
        self, layer: str, player_id: str = "default", limit: int = 50
    ) -> list:
        """Get all memories in a layer for a player."""
        cur = self._conn.execute(
            """SELECT * FROM memories
               WHERE layer = ? AND player_id = ?
               ORDER BY accessed_at DESC
               LIMIT ?""",
            (layer, player_id, limit),
        )
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def search_similar(
        self,
        query_embedding: "np.ndarray",
        top_k: int = 5,
        layer: str = None,
        player_id: str = "default",
    ) -> list:
        """Cosine similarity search across memories. Returns top-k similar."""
        where = "WHERE embedding IS NOT NULL AND player_id = ?"
        params: list = [player_id]
        if layer:
            where += " AND layer = ?"
            params.append(layer)

        cur = self._conn.execute(f"SELECT * FROM memories {where}", params)
        rows = cur.fetchall()

        scored = []
        q_norm = np.linalg.norm(query_embedding)
        for row in rows:
            emb = np.frombuffer(row["embedding"], dtype=np.float64)
            e_norm = np.linalg.norm(emb)
            if q_norm == 0 or e_norm == 0:
                sim = 0.0
            else:
                sim = float(np.dot(query_embedding, emb) / (q_norm * e_norm))
            scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._row_to_dict(r) for _, r in scored[:top_k]]

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory and its connections. Returns True if deleted."""
        cur = self._conn.execute(
            "DELETE FROM memories WHERE id = ?", (memory_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def add_connection(
        self,
        source_id: int,
        target_id: int,
        relationship: str,
        weight: float = 1.0,
    ) -> int:
        """Create a connection between two memories. Returns connection ID."""
        cur = self._conn.execute(
            """INSERT INTO connections (source_id, target_id, relationship, weight)
               VALUES (?, ?, ?, ?)""",
            (source_id, target_id, relationship, weight),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_connections(self, memory_id: int) -> list:
        """Get all connections for a memory (both directions)."""
        cur = self._conn.execute(
            """SELECT * FROM connections
               WHERE source_id = ? OR target_id = ?""",
            (memory_id, memory_id),
        )
        return [dict(r) for r in cur.fetchall()]

    def update_strength(self, memory_id: int, new_strength: float):
        """Update memory strength."""
        self._conn.execute(
            "UPDATE memories SET strength = ? WHERE id = ?",
            (new_strength, memory_id),
        )
        self._conn.commit()

    def get_stats(self, player_id: str = "default") -> dict:
        """Return count of memories per layer + total connections."""
        cur = self._conn.execute(
            """SELECT layer, COUNT(*) as cnt
               FROM memories WHERE player_id = ?
               GROUP BY layer""",
            (player_id,),
        )
        layer_counts = {r["layer"]: r["cnt"] for r in cur.fetchall()}

        cur2 = self._conn.execute(
            """SELECT COUNT(*) as cnt FROM connections
               WHERE source_id IN (SELECT id FROM memories WHERE player_id = ?)
                  OR target_id IN (SELECT id FROM memories WHERE player_id = ?)""",
            (player_id, player_id),
        )
        total_connections = cur2.fetchone()["cnt"]

        return {
            "layer_counts": layer_counts,
            "total_memories": sum(layer_counts.values()),
            "total_connections": total_connections,
        }
