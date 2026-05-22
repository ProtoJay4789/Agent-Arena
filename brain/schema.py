"""SQLite schema for Echo Brain's 4-layer memory architecture."""
import sqlite3


SCHEMA_SQL = """
-- Core memories table (all layers share this)
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    layer TEXT NOT NULL CHECK(layer IN ('working', 'short_term', 'long_term')),
    content TEXT NOT NULL,
    embedding BLOB,  -- numpy array serialized
    tags TEXT DEFAULT '{}',  -- JSON dict
    metadata TEXT DEFAULT '{}',  -- JSON dict
    strength REAL DEFAULT 1.0,  -- 0.0 to 1.0, decays over time
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    player_id TEXT DEFAULT 'default'
);

-- Connection graph between memories
CREATE TABLE IF NOT EXISTS connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    relationship TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_memories_layer ON memories(layer);
CREATE INDEX IF NOT EXISTS idx_memories_player ON memories(player_id);
CREATE INDEX IF NOT EXISTS idx_connections_source ON connections(source_id);
CREATE INDEX IF NOT EXISTS idx_connections_target ON connections(target_id);
"""


def init_db(db_path: str = "echo_brain.db") -> sqlite3.Connection:
    """Create the database, apply schema, and return a connection.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        An open sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
