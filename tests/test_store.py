"""Tests for Echo Brain MemoryStore."""
import numpy as np
import pytest

from brain.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    """Create a fresh MemoryStore with a temp database for each test."""
    db_path = str(tmp_path / "test_echo_brain.db")
    return MemoryStore(db_path=db_path)


# ------------------------------------------------------------------
# Basic CRUD
# ------------------------------------------------------------------


def test_add_and_retrieve_memory(store):
    """Adding a memory and retrieving it returns correct data."""
    mid = store.add_memory(
        content="The dragon is in the cave",
        layer="working",
        tags={"danger": True},
        metadata={"source": "observation"},
    )
    assert isinstance(mid, int)
    assert mid > 0

    mem = store.get_memory(mid)
    assert mem is not None
    assert mem["id"] == mid
    assert mem["content"] == "The dragon is in the cave"
    assert mem["layer"] == "working"
    assert mem["tags"] == {"danger": True}
    assert mem["metadata"] == {"source": "observation"}
    assert mem["player_id"] == "default"
    assert mem["strength"] == 1.0


def test_get_nonexistent_memory(store):
    """Getting a non-existent memory returns None."""
    assert store.get_memory(99999) is None


# ------------------------------------------------------------------
# Query by layer
# ------------------------------------------------------------------


def test_query_by_layer(store):
    """Querying by layer returns only memories in that layer."""
    store.add_memory("Working 1", layer="working", player_id="p1")
    store.add_memory("Working 2", layer="working", player_id="p1")
    store.add_memory("Short 1", layer="short_term", player_id="p1")
    store.add_memory("Long 1", layer="long_term", player_id="p1")

    working = store.query_by_layer("working", player_id="p1")
    assert len(working) == 2
    assert all(m["layer"] == "working" for m in working)

    short = store.query_by_layer("short_term", player_id="p1")
    assert len(short) == 1


# ------------------------------------------------------------------
# Similarity search
# ------------------------------------------------------------------


def test_search_similar(store):
    """Cosine similarity search returns results in correct order."""
    dim = 128
    np.random.seed(42)

    # Create 3 memories with known embeddings
    emb_a = np.random.randn(dim).astype(np.float64)
    emb_b = np.random.randn(dim).astype(np.float64)
    # emb_c is similar to emb_a (add small noise)
    emb_c = emb_a + np.random.randn(dim).astype(np.float64) * 0.01

    store.add_memory("A", layer="long_term", embedding=emb_a)
    store.add_memory("B", layer="long_term", embedding=emb_b)
    store.add_memory("C (similar to A)", layer="long_term", embedding=emb_c)

    # Search with emb_a as query
    results = store.search_similar(emb_a, top_k=3, layer="long_term")
    assert len(results) >= 2
    # First result should be the memory with embedding emb_a itself (exact match)
    assert results[0]["content"] == "A"
    # Second result should be the similar one (C)
    assert results[1]["content"] == "C (similar to A)"


def test_search_similar_with_layer_filter(store):
    """Search only returns memories from the specified layer."""
    dim = 64
    emb = np.random.randn(dim).astype(np.float64)

    store.add_memory("Working", layer="working", embedding=emb)
    store.add_memory("Long", layer="long_term", embedding=emb)

    results = store.search_similar(emb, layer="working")
    assert len(results) == 1
    assert results[0]["layer"] == "working"


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------


def test_delete_memory(store):
    """Deleting a memory removes it and its connections."""
    mid1 = store.add_memory("M1", layer="working")
    mid2 = store.add_memory("M2", layer="working")
    store.add_connection(mid1, mid2, "related")

    # Verify connection exists
    conns = store.get_connections(mid1)
    assert len(conns) == 1

    deleted = store.delete_memory(mid1)
    assert deleted is True

    assert store.get_memory(mid1) is None
    # Connection should be cascade-deleted
    assert store.get_connections(mid2) == []


def test_delete_nonexistent(store):
    """Deleting a non-existent memory returns False."""
    assert store.delete_memory(99999) is False


# ------------------------------------------------------------------
# Connections
# ------------------------------------------------------------------


def test_add_and_get_connections(store):
    """Adding connections and retrieving them works both directions."""
    mid1 = store.add_memory("A", layer="working")
    mid2 = store.add_memory("B", layer="working")
    mid3 = store.add_memory("C", layer="working")

    store.add_connection(mid1, mid2, "causes")
    store.add_connection(mid2, mid3, "prevents")

    # Get connections for mid2 — should see both (source and target)
    conns = store.get_connections(mid2)
    assert len(conns) == 2

    relationships = {c["relationship"] for c in conns}
    assert "causes" in relationships
    assert "prevents" in relationships


# ------------------------------------------------------------------
# Strength
# ------------------------------------------------------------------


def test_update_strength(store):
    """Updating strength persists the new value."""
    mid = store.add_memory("M", layer="working")
    store.update_strength(mid, 0.3)
    mem = store.get_memory(mid)
    assert mem["strength"] == pytest.approx(0.3)


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------


def test_get_stats(store):
    """Stats returns correct counts per layer and total connections."""
    store.add_memory("W1", layer="working", player_id="p1")
    store.add_memory("W2", layer="working", player_id="p1")
    store.add_memory("S1", layer="short_term", player_id="p1")

    mid1 = store.add_memory("W3", layer="working", player_id="p1")
    mid2 = store.add_memory("S2", layer="short_term", player_id="p1")
    store.add_connection(mid1, mid2, "related")

    stats = store.get_stats(player_id="p1")
    assert stats["total_memories"] == 5
    assert stats["layer_counts"]["working"] == 3
    assert stats["layer_counts"]["short_term"] == 2
    assert stats["total_connections"] == 1


# ------------------------------------------------------------------
# Player isolation
# ------------------------------------------------------------------


def test_player_isolation(store):
    """Different player_ids don't see each other's memories."""
    store.add_memory("Alpha", layer="working", player_id="player_A")
    store.add_memory("Beta", layer="working", player_id="player_B")
    store.add_memory("Gamma", layer="long_term", player_id="player_A")

    a_working = store.query_by_layer("working", player_id="player_A")
    b_working = store.query_by_layer("working", player_id="player_B")

    assert len(a_working) == 1
    assert a_working[0]["content"] == "Alpha"
    assert len(b_working) == 1
    assert b_working[0]["content"] == "Beta"

    a_long = store.query_by_layer("long_term", player_id="player_A")
    assert len(a_long) == 1

    # Stats should be isolated too
    stats_a = store.get_stats("player_A")
    stats_b = store.get_stats("player_B")
    assert stats_a["total_memories"] == 2
    assert stats_b["total_memories"] == 1
