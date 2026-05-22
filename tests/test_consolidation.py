"""Tests for ConsolidationEngine."""
import pytest

from brain.store import MemoryStore
from brain.consolidation import ConsolidationEngine


@pytest.fixture
def store(tmp_path):
    """Fresh MemoryStore for each test."""
    return MemoryStore(db_path=str(tmp_path / "test_consolidation.db"))


@pytest.fixture
def engine(store):
    """ConsolidationEngine wrapping the fixture store."""
    return ConsolidationEngine(store=store)


# ------------------------------------------------------------------
# Decay
# ------------------------------------------------------------------


def test_decay_reduces_strength(engine, store):
    """Short-term memories lose strength over time."""
    mid = store.add_memory("Fading memory", layer="short_term")
    store.update_strength(mid, 1.0)

    count = engine.decay_short_term(days_elapsed=2.0, decay_rate=0.1)
    assert count == 1

    mem = store.get_memory(mid)
    assert mem["strength"] == pytest.approx(0.8)  # 1.0 - 0.1*2


def test_decay_clamps_to_zero(engine, store):
    """Strength never goes below 0."""
    mid = store.add_memory("Almost dead", layer="short_term")
    store.update_strength(mid, 0.05)

    engine.decay_short_term(days_elapsed=5.0, decay_rate=0.1)
    mem = store.get_memory(mid)
    assert mem["strength"] == pytest.approx(0.0)


def test_decay_ignores_other_layers(engine, store):
    """Only short_term memories are decayed."""
    store.add_memory("Working memory", layer="working")
    st = store.add_memory("Short term", layer="short_term")
    store.add_memory("Long term", layer="long_term")

    count = engine.decay_short_term(days_elapsed=1.0, decay_rate=0.1)
    assert count == 1

    working = store.query_by_layer("working")
    long = store.query_by_layer("long_term")
    assert working[0]["strength"] == 1.0
    assert long[0]["strength"] == 1.0


# ------------------------------------------------------------------
# Promotion
# ------------------------------------------------------------------


def test_promote_by_access_count(engine, store):
    """Short-term memory promoted when access_count >= threshold."""
    mid = store.add_memory("Frequently accessed", layer="short_term")
    # Simulate high access count directly in DB
    store._conn.execute(
        "UPDATE memories SET access_count = 5 WHERE id = ?", (mid,)
    )
    store._conn.commit()

    count = engine.promote_to_long_term(access_threshold=3)
    assert count == 1

    mem = store.get_memory(mid)
    assert mem["layer"] == "long_term"


def test_promote_by_strength(engine, store):
    """Short-term memory promoted when strength >= threshold."""
    mid = store.add_memory("Strong memory", layer="short_term")
    store.update_strength(mid, 0.8)

    count = engine.promote_to_long_term(strength_threshold=0.5)
    assert count == 1

    mem = store.get_memory(mid)
    assert mem["layer"] == "long_term"


def test_no_promote_below_threshold(engine, store):
    """Low-access, low-strength memories stay in short_term."""
    mid = store.add_memory("Weak memory", layer="short_term")
    store.update_strength(mid, 0.2)

    count = engine.promote_to_long_term(access_threshold=3, strength_threshold=0.5)
    assert count == 0

    mem = store.get_memory(mid)
    assert mem["layer"] == "short_term"


# ------------------------------------------------------------------
# Remove dead
# ------------------------------------------------------------------


def test_remove_dead_memories(engine, store):
    """Memories with strength <= 0 are deleted."""
    mid1 = store.add_memory("Dead one", layer="short_term")
    store.update_strength(mid1, 0.0)

    mid2 = store.add_memory("Alive one", layer="short_term")
    store.update_strength(mid2, 0.1)

    removed = engine.remove_dead_memories()
    assert removed == 1
    assert store.get_memory(mid1) is None
    assert store.get_memory(mid2) is not None


# ------------------------------------------------------------------
# Full consolidation cycle
# ------------------------------------------------------------------


def test_consolidate_full_cycle(engine, store):
    """consolidate() runs decay → promote → remove and returns counts."""
    # Memory A: short-term, will decay to 0 and be removed
    mid_a = store.add_memory("Dying memory", layer="short_term")
    store.update_strength(mid_a, 0.05)

    # Memory B: short-term, strong enough to promote
    mid_b = store.add_memory("Strong memory", layer="short_term")
    store.update_strength(mid_b, 0.9)

    # Memory C: dead on arrival
    mid_c = store.add_memory("Already dead", layer="short_term")
    store.update_strength(mid_c, 0.0)

    result = engine.consolidate(days_elapsed=1.0)
    assert isinstance(result, dict)
    assert "decayed" in result
    assert "promoted" in result
    assert "removed" in result

    # A should have been decayed (0.05 - 0.1 = clamped to 0), then removed
    assert store.get_memory(mid_a) is None
    # B should have been promoted (strength 0.9 > 0.5)
    mem_b = store.get_memory(mid_b)
    assert mem_b["layer"] == "long_term"
    # C should have been removed (strength 0)
    assert store.get_memory(mid_c) is None


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------


def test_get_stats(engine, store):
    """get_stats returns correct layer counts and strength info."""
    store.add_memory("W1", layer="working", player_id="p1")
    store.add_memory("W2", layer="working", player_id="p1")
    store.add_memory("S1", layer="short_term", player_id="p1")
    store.add_memory("L1", layer="long_term", player_id="p1")
    store.update_strength(store.add_memory("Weak", layer="short_term", player_id="p1"), 0.1)

    stats = engine.get_stats(player_id="p1")
    assert stats["working"] == 2
    assert stats["short_term"] == 2
    assert stats["long_term"] == 1
    assert "avg_strength" in stats
    assert "weakest_memories" in stats
    assert isinstance(stats["weakest_memories"], list)
    # Weakest should come first
    if stats["weakest_memories"]:
        assert stats["weakest_memories"][0]["content"] == "Weak"
