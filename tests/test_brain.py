"""Tests for Echo Brain — Memory architecture for AI agents."""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from brain.schema import init_db
from brain.store import MemoryStore
from brain.pipeline import MemoryPipeline
from brain.tagger import TradeTagger
from brain.consolidation import ConsolidationEngine
from brain.patterns import PatternDetector


# ── Schema Tests ─────────────────────────────────────────────────────────

def test_init_db_creates_tables():
    """Database should have memories and connections tables."""
    conn = init_db(":memory:")
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t['name'] for t in tables]
    assert 'memories' in table_names
    assert 'connections' in table_names


def test_init_db_idempotent():
    """Calling init_db twice shouldn't error."""
    conn = init_db(":memory:")
    conn2 = init_db(":memory:")
    assert conn is not None


# ── Store Tests ──────────────────────────────────────────────────────────

def test_add_memory():
    """Should add a memory and return its ID."""
    store = MemoryStore(":memory:")
    mid = store.add_memory(content="Bought SOL at $150", layer="working")
    assert mid is not None
    assert mid > 0


def test_add_memory_with_tags():
    """Should store tags as JSON."""
    store = MemoryStore(":memory:")
    mid = store.add_memory(
        content="Sold ETH for profit",
        layer="short_term",
        tags={"action": "sell", "token": "ETH"},
    )
    mem = store.get_memory(mid)
    assert mem is not None
    assert mem['tags']['action'] == 'sell'


def test_get_memory():
    """Should retrieve a memory by ID."""
    store = MemoryStore(":memory:")
    mid = store.add_memory(content="Test memory", layer="working")
    mem = store.get_memory(mid)
    assert mem is not None
    assert mem['content'] == "Test memory"
    assert mem['layer'] == "working"


def test_get_memory_not_found():
    """Should return None for non-existent memory."""
    store = MemoryStore(":memory:")
    mem = store.get_memory(99999)
    assert mem is None


def test_delete_memory():
    """Should delete a memory."""
    store = MemoryStore(":memory:")
    mid = store.add_memory(content="Delete me", layer="working")
    assert store.delete_memory(mid) is True
    assert store.get_memory(mid) is None


def test_delete_memory_not_found():
    """Should return False for non-existent memory."""
    store = MemoryStore(":memory:")
    assert store.delete_memory(99999) is False


def test_query_by_layer():
    """Should query memories by layer."""
    store = MemoryStore(":memory:")
    store.add_memory(content="Working 1", layer="working")
    store.add_memory(content="Working 2", layer="working")
    store.add_memory(content="Short-term 1", layer="short_term")

    working = store.query_by_layer("working")
    assert len(working) == 2

    short_term = store.query_by_layer("short_term")
    assert len(short_term) == 1


def test_update_strength():
    """Should update memory strength."""
    store = MemoryStore(":memory:")
    mid = store.add_memory(content="Test", layer="working")
    store.update_strength(mid, 0.5)
    mem = store.get_memory(mid)
    assert mem['strength'] == 0.5


def test_search_similar():
    """Should find memories by embedding similarity."""
    store = MemoryStore(":memory:")
    
    emb1 = np.random.randn(128).astype(np.float64)
    emb1 /= np.linalg.norm(emb1)
    
    emb2 = np.random.randn(128).astype(np.float64)
    emb2 /= np.linalg.norm(emb2)
    
    store.add_memory(content="Memory A", layer="working", embedding=emb1)
    store.add_memory(content="Memory B", layer="working", embedding=emb2)
    
    results = store.search_similar(query_embedding=emb1, top_k=1)
    assert len(results) == 1
    assert results[0]['content'] == "Memory A"


def test_connections():
    """Should create and query connections between memories."""
    store = MemoryStore(":memory:")
    m1 = store.add_memory(content="Bought SOL", layer="working")
    m2 = store.add_memory(content="SOL went up 20%", layer="working")
    
    store.add_connection(m1, m2, "caused", weight=0.9)
    
    conns = store.get_connections(m1)
    assert len(conns) == 1
    assert conns[0]['relationship'] == "caused"


def test_get_stats():
    """Should return memory statistics."""
    store = MemoryStore(":memory:")
    store.add_memory(content="Test 1", layer="working")
    store.add_memory(content="Test 2", layer="short_term")
    
    stats = store.get_stats()
    assert stats['total_memories'] == 2
    assert 'working' in stats['layer_counts']


# ── Pipeline Tests ───────────────────────────────────────────────────────

def test_pipeline_embed_text():
    """Embedding should be deterministic for same text."""
    store = MemoryStore(":memory:")
    pipeline = MemoryPipeline(store)
    
    emb1 = pipeline.embed_text("hello world")
    emb2 = pipeline.embed_text("hello world")
    
    assert emb1.shape == (128,)
    assert np.allclose(emb1, emb2)


def test_pipeline_embed_text_different():
    """Different text should produce different embeddings."""
    store = MemoryStore(":memory:")
    pipeline = MemoryPipeline(store)
    
    emb1 = pipeline.embed_text("hello world")
    emb2 = pipeline.embed_text("goodbye world")
    
    assert not np.allclose(emb1, emb2)


def test_pipeline_process_event():
    """Should process an event into a stored memory."""
    store = MemoryStore(":memory:")
    pipeline = MemoryPipeline(store)
    
    mid = pipeline.process_event({
        "content": "Bought 10 SOL at $150",
        "layer": "working",
        "tags": {"action": "buy"},
        "player_id": "jordan",
    })
    
    assert mid > 0
    mem = store.get_memory(mid)
    assert mem['content'] == "Bought 10 SOL at $150"
    assert mem['tags']['action'] == 'buy'


def test_pipeline_retrieve_context():
    """Should retrieve relevant memories for a query."""
    store = MemoryStore(":memory:")
    pipeline = MemoryPipeline(store)
    
    pipeline.store_with_embedding("Bought SOL at $150", layer="working")
    pipeline.store_with_embedding("Sold ETH for profit", layer="working")
    pipeline.store_with_embedding("Market crashed today", layer="short_term")
    
    results = pipeline.retrieve_context("SOL purchase", top_k=2)
    assert len(results) <= 2


def test_pipeline_store_with_embedding():
    """Should embed and store in one step."""
    store = MemoryStore(":memory:")
    pipeline = MemoryPipeline(store)
    
    mid = pipeline.store_with_embedding(
        "Bought 100 DOGE at $0.10",
        layer="working",
        tags={"token": "DOGE"},
    )
    
    assert mid > 0
    mem = store.get_memory(mid)
    assert mem is not None
    assert mem['embedding'] is not None


# ── Tagger Tests ─────────────────────────────────────────────────────────

def test_tagger_basic():
    """Tagger should identify trade actions."""
    store = MemoryStore(":memory:")
    tagger = TradeTagger(store)
    tags = tagger.tag_trade({"action": "buy", "token": "SOL", "amount": 10})
    assert 'action' in tags
    assert tags['action'] == 'buy'


def test_tagger_store_trade():
    """Tagger should store tagged trades."""
    store = MemoryStore(":memory:")
    tagger = TradeTagger(store)
    
    tagged = tagger.tag_trade({
        "action": "sell",
        "token": "ETH",
        "amount": 5,
        "price": 3000,
    })
    mid = tagger.store_trade(tagged)
    assert mid > 0


def test_tagger_history():
    """Tagger should retrieve trade history."""
    store = MemoryStore(":memory:")
    tagger = TradeTagger(store)
    
    tagged = tagger.tag_trade({"action": "buy", "token": "SOL", "amount": 10})
    tagger.store_trade(tagged)
    
    history = tagger.get_trade_history()
    assert len(history) > 0


# ── Consolidation Tests ──────────────────────────────────────────────────

def test_consolidation_decay():
    """Should decay short-term memory strength."""
    store = MemoryStore(":memory:")
    consolidation = ConsolidationEngine(store)
    
    store.add_memory(content="Decay me", layer="short_term")
    count = consolidation.decay_short_term(days_elapsed=1.0, decay_rate=0.5)
    assert count > 0


def test_consolidation_promote():
    """Should promote short-term memories to long-term."""
    store = MemoryStore(":memory:")
    consolidation = ConsolidationEngine(store)
    
    mid = store.add_memory(content="Promote me", layer="short_term")
    store.update_strength(mid, 0.8)
    store._conn.execute(
        "UPDATE memories SET access_count = 5 WHERE id = ?", (mid,)
    )
    store._conn.commit()
    
    count = consolidation.promote_to_long_term(access_threshold=3, strength_threshold=0.5)
    assert count > 0
    
    mem = store.get_memory(mid)
    assert mem['layer'] == 'long_term'


def test_consolidation_remove_dead():
    """Should remove memories with zero strength."""
    store = MemoryStore(":memory:")
    consolidation = ConsolidationEngine(store)
    
    mid = store.add_memory(content="Dead memory", layer="short_term")
    store.update_strength(mid, 0.0)
    
    count = consolidation.remove_dead_memories()
    assert count > 0
    assert store.get_memory(mid) is None


def test_consolidation_full_cycle():
    """Full consolidation cycle should run without error."""
    store = MemoryStore(":memory:")
    consolidation = ConsolidationEngine(store)
    
    store.add_memory(content="Test 1", layer="short_term")
    store.add_memory(content="Test 2", layer="short_term")
    
    result = consolidation.consolidate(days_elapsed=1.0)
    assert 'decayed' in result
    assert 'promoted' in result
    assert 'removed' in result


# ── Pattern Detection Tests ──────────────────────────────────────────────

def test_pattern_frequency():
    """Should analyze trade frequency patterns."""
    store = MemoryStore(":memory:")
    pipeline = MemoryPipeline(store)
    patterns = PatternDetector(store)
    
    pipeline.process_event({
        "content": "Bought SOL",
        "layer": "short_term",
        "tags": {"action": "buy"},
    })
    
    result = patterns.analyze_frequency()
    assert 'avg_trades_per_day' in result


def test_pattern_timing():
    """Should analyze trade timing patterns."""
    store = MemoryStore(":memory:")
    patterns = PatternDetector(store)
    
    result = patterns.analyze_timing()
    assert 'best_trading_hours' in result


# ── Integration Tests ────────────────────────────────────────────────────

def test_full_memory_lifecycle():
    """Test complete memory lifecycle: store → tag → pattern → consolidate."""
    store = MemoryStore(":memory:")
    pipeline = MemoryPipeline(store)
    tagger = TradeTagger(store)
    patterns = PatternDetector(store)
    consolidation = ConsolidationEngine(store)
    
    # 1. Process events
    events = [
        {"content": "Bought SOL at $150", "layer": "working"},
        {"content": "Bought ETH at $3000", "layer": "working"},
        {"content": "SOL went up to $180", "layer": "short_term"},
        {"content": "Sold SOL for profit", "layer": "short_term"},
    ]
    
    for event in events:
        mid = pipeline.process_event(event)
        assert mid > 0
    
    # 2. Check all memories stored
    stats = store.get_stats()
    assert stats['total_memories'] == 4
    
    # 3. Tag trades
    tagged = tagger.tag_trade({"action": "buy", "token": "SOL", "amount": 10})
    assert 'action' in tagged
    
    # 4. Detect patterns
    freq = patterns.analyze_frequency()
    assert freq is not None
    
    # 5. Consolidate
    result = consolidation.consolidate(days_elapsed=1.0)
    assert result is not None


def test_memory_with_embedding():
    """Full flow with embeddings."""
    store = MemoryStore(":memory:")
    pipeline = MemoryPipeline(store)
    
    mid = pipeline.store_with_embedding(
        "Bought 100 DOGE at $0.10",
        layer="working",
        tags={"token": "DOGE"},
    )
    
    mem = store.get_memory(mid)
    results = store.search_similar(
        query_embedding=mem['embedding'],
        top_k=1,
    )
    assert len(results) == 1
    assert results[0]['id'] == mid
