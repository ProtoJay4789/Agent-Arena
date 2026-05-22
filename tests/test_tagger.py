"""Tests for TradeTagger."""
import json
import pytest
from brain.store import MemoryStore
from brain.tagger import TradeTagger


@pytest.fixture
def store():
    return MemoryStore(db_path=":memory:")


@pytest.fixture
def tagger(store):
    return TradeTagger(store)


# ------------------------------------------------------------------
# tag_trade
# ------------------------------------------------------------------

def test_tag_trade_adds_context(tagger):
    """tag_trade returns dict with market_conditions and emotional_state."""
    trade = {
        "action": "buy",
        "token": "SOL",
        "amount": 10,
        "price": 100,
        "price_1h_ago": 100,
        "timestamp": "2026-05-01T12:00:00",
        "player_id": "test_player",
    }
    tagged = tagger.tag_trade(trade)
    assert "tags" in tagged
    assert "market_conditions" in tagged["tags"]
    assert "emotional_state" in tagged["tags"]
    assert tagged["tags"]["market_conditions"] in ("volatile", "stable", "calm")
    assert tagged["tags"]["emotional_state"] in ("fomo", "panic", "confident", "neutral")


def test_emotional_state_fomo(tagger):
    """Large trade amount triggers fomo."""
    # First store a small trade to set baseline
    small_trade = {
        "action": "buy", "token": "ETH", "amount": 1,
        "price": 2000, "price_1h_ago": 2000,
        "timestamp": "2026-05-01T10:00:00", "player_id": "p1",
    }
    tagger.store_trade(tagger.tag_trade(small_trade))

    # Now a trade > 2x average
    big_trade = {
        "action": "buy", "token": "ETH", "amount": 5,
        "price": 2000, "price_1h_ago": 2000,
        "timestamp": "2026-05-01T11:00:00", "player_id": "p1",
    }
    tagged = tagger.tag_trade(big_trade)
    assert tagged["tags"]["emotional_state"] == "fomo"


def test_emotional_state_panic(tagger):
    """Sell after recent losses triggers panic."""
    # Store a losing trade first
    losing = {
        "action": "buy", "token": "BTC", "amount": 1,
        "price": 50000, "price_1h_ago": 50000,
        "timestamp": "2026-05-01T09:00:00", "player_id": "p2",
    }
    trade_id = tagger.store_trade(tagger.tag_trade(losing))
    tagger.resolve_trade(trade_id, {"pnl": -100, "duration_minutes": 5, "success": False})

    # Now a sell
    sell = {
        "action": "sell", "token": "BTC", "amount": 1,
        "price": 49000, "price_1h_ago": 50000,
        "timestamp": "2026-05-01T10:00:00", "player_id": "p2",
    }
    tagged = tagger.tag_trade(sell)
    assert tagged["tags"]["emotional_state"] == "panic"


def test_market_conditions_volatile(tagger):
    """Large price swing triggers volatile."""
    trade = {
        "action": "buy", "token": "SOL", "amount": 10,
        "price": 110, "price_1h_ago": 100,
        "timestamp": "2026-05-01T12:00:00", "player_id": "test",
    }
    tagged = tagger.tag_trade(trade)
    assert tagged["tags"]["market_conditions"] == "volatile"  # 10% change


def test_market_conditions_stable(tagger):
    """Moderate price swing triggers stable."""
    trade = {
        "action": "buy", "token": "SOL", "amount": 10,
        "price": 103, "price_1h_ago": 100,
        "timestamp": "2026-05-01T12:00:00", "player_id": "test",
    }
    tagged = tagger.tag_trade(trade)
    assert tagged["tags"]["market_conditions"] == "stable"  # 3% change


# ------------------------------------------------------------------
# store_trade
# ------------------------------------------------------------------

def test_store_trade_persists(tagger, store):
    """Stored trade is retrievable from MemoryStore."""
    trade = {
        "action": "buy", "token": "SOL", "amount": 10,
        "price": 100, "price_1h_ago": 100,
        "timestamp": "2026-05-01T12:00:00", "player_id": "p3",
    }
    tagged = tagger.tag_trade(trade)
    memory_id = tagger.store_trade(tagged)
    assert memory_id is not None and memory_id > 0

    memory = store.get_memory(memory_id)
    assert memory is not None
    content = json.loads(memory["content"])
    assert content["token"] == "SOL"
    assert memory["player_id"] == "p3"


# ------------------------------------------------------------------
# resolve_trade
# ------------------------------------------------------------------

def test_resolve_trade_updates_outcome(tagger):
    """resolve_trade writes outcome into tags and metadata."""
    trade = {
        "action": "buy", "token": "ETH", "amount": 1,
        "price": 2000, "price_1h_ago": 2000,
        "timestamp": "2026-05-01T12:00:00", "player_id": "p4",
    }
    tagged = tagger.tag_trade(trade)
    memory_id = tagger.store_trade(tagged)

    outcome = {"pnl": 150.5, "duration_minutes": 30, "success": True}
    updated = tagger.resolve_trade(memory_id, outcome)

    assert updated["tags"]["outcome"]["pnl"] == 150.5
    assert updated["tags"]["outcome"]["success"] is True
    assert updated["metadata"]["pnl"] == 150.5
    assert updated["metadata"]["success"] is True


def test_resolve_trade_not_found(tagger):
    """resolve_trade raises ValueError for unknown id."""
    with pytest.raises(ValueError):
        tagger.resolve_trade(999999, {"pnl": 0, "duration_minutes": 0, "success": False})


# ------------------------------------------------------------------
# get_trade_history
# ------------------------------------------------------------------

def test_get_trade_history(tagger):
    """get_trade_history returns stored trades."""
    for i in range(3):
        trade = {
            "action": "buy", "token": "SOL", "amount": i + 1,
            "price": 100, "price_1h_ago": 100,
            "timestamp": f"2026-05-01T{10 + i}:00:00", "player_id": "p5",
        }
        tagged = tagger.tag_trade(trade)
        tagger.store_trade(tagged)

    history = tagger.get_trade_history("p5")
    assert len(history) == 3
