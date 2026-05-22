"""Integration test — full Echo Brain workflow.

Simulates a player making trades over multiple days, the brain tagging
them, detecting patterns, consolidating memories, and retrieving context.
"""
import pytest
from datetime import datetime, timedelta

from brain.store import MemoryStore
from brain.tagger import TradeTagger
from brain.pipeline import MemoryPipeline
from brain.patterns import PatternDetector
from brain.consolidation import ConsolidationEngine


@pytest.fixture
def brain():
    """Fresh in-memory brain with all components wired."""
    store = MemoryStore(":memory:")
    return {
        "store": store,
        "tagger": TradeTagger(store),
        "pipeline": MemoryPipeline(store),
        "patterns": PatternDetector(store),
        "consolidation": ConsolidationEngine(store),
    }


def _make_trade(action, token, amount, price, reasoning="", offset_days=0):
    """Helper to create a trade dict with a timestamp offset."""
    ts = datetime(2026, 5, 15, 10, 0) + timedelta(days=offset_days)
    return {
        "action": action,
        "token": token,
        "amount": amount,
        "price": price,
        "timestamp": ts.isoformat(),
        "reasoning": reasoning,
        "player_id": "test_player",
    }


class TestFullWorkflow:
    """End-to-end: player trades, brain learns, brain advises."""

    def test_trade_lifecycle(self, brain):
        """Trades flow through tagging → storage → retrieval."""
        tagger = brain["tagger"]
        store = brain["store"]

        # Player makes a trade
        trade = _make_trade("buy", "ETH", 1000, 3500, "Bullish on merge")
        tagged = tagger.tag_trade(trade)

        assert tagged["tags"]["emotional_state"] in ("neutral", "confident", "fomo")
        assert tagged["tags"]["market_conditions"] in ("calm", "stable", "volatile")

        # Store it
        memory_id = tagger.store_trade(tagged)
        assert memory_id is not None
        assert memory_id > 0

        # Retrieve it
        history = tagger.get_trade_history("test_player")
        assert len(history) == 1
        assert "ETH" in history[0]["content"]

    def test_pattern_detection_after_trades(self, brain):
        """After multiple trades, patterns emerge."""
        tagger = brain["tagger"]
        patterns = brain["patterns"]

        # Player makes 5 trades over 5 days
        trades = [
            _make_trade("buy", "ETH", 1000, 3500, offset_days=0),
            _make_trade("sell", "ETH", 1200, 3600, offset_days=1),
            _make_trade("buy", "SOL", 500, 150, offset_days=2),
            _make_trade("buy", "ARB", 800, 1.2, "FOMO", offset_days=3),
            _make_trade("sell", "SOL", 600, 140, "Panic", offset_days=4),
        ]

        for trade in trades:
            tagged = tagger.tag_trade(trade)
            tagger.store_trade(tagged)
            # Resolve some as wins, some as losses
            if trade["action"] == "sell":
                tagger.resolve_trade(
                    trade_id=tagger.get_trade_history("test_player")[-1]["id"],
                    outcome={"pnl": 100 if trade["amount"] > 500 else -50,
                             "duration_minutes": 1440, "success": True}
                )

        # Patterns should be detectable
        freq = patterns.analyze_frequency("test_player")
        assert len(freq["trades_per_day"]) >= 3  # trades across multiple days

        outcomes = patterns.analyze_outcomes("test_player")
        assert outcomes["total_trades"] >= 2  # only resolved trades counted

    def test_consolidation_cycle(self, brain):
        """Memories decay and promote correctly over time."""
        store = brain["store"]
        consolidation = brain["consolidation"]

        # Add some short-term memories
        for i in range(5):
            store.add_memory(
                content=f"Trade {i} happened",
                layer="short_term",
                tags={"trade_id": i},
                player_id="test_player",
            )

        # Verify they exist
        stats = consolidation.get_stats("test_player")
        assert stats["short_term"] == 5

        # Run consolidation — decay reduces strength, promotion moves strong ones
        result = consolidation.consolidate(days_elapsed=0.5)
        assert result["decayed"] == 5

        # After consolidation: strong memories (strength >= 0.5) promoted to long_term
        stats = consolidation.get_stats("test_player")
        # Memories start at 1.0, decay by 0.1 * 0.5 = 0.05 → strength 0.95
        # 0.95 >= 0.5 threshold → all promoted to long_term
        assert stats["long_term"] == 5
        assert stats["short_term"] == 0

    def test_pipeline_end_to_end(self, brain):
        """Pipeline processes events and retrieves by similarity."""
        pipeline = brain["pipeline"]

        # Process some events
        events = [
            {"content": "Player bought ETH at $3500", "layer": "short_term",
             "tags": {"token": "ETH"}, "player_id": "test_player"},
            {"content": "Player sold SOL at $150", "layer": "short_term",
             "tags": {"token": "SOL"}, "player_id": "test_player"},
            {"content": "Player is bullish on ETH", "layer": "long_term",
             "tags": {"sentiment": "bullish"}, "player_id": "test_player"},
        ]

        ids = [pipeline.process_event(e) for e in events]
        assert len(ids) == 3
        assert all(i > 0 for i in ids)

        # Retrieve context — should find relevant memories
        results = pipeline.retrieve_context("ETH trade", "test_player", top_k=3)
        assert len(results) > 0

    def test_player_isolation(self, brain):
        """Different players don't see each other's memories."""
        store = brain["store"]

        store.add_memory("Player 1 trade", "short_term", player_id="player_1")
        store.add_memory("Player 2 trade", "short_term", player_id="player_2")

        p1 = store.query_by_layer("short_term", "player_1")
        p2 = store.query_by_layer("short_term", "player_2")

        assert len(p1) == 1
        assert len(p2) == 1
        assert "Player 1" in p1[0]["content"]
        assert "Player 2" in p2[0]["content"]

    def test_connection_graph(self, brain):
        """Memories can be connected in a graph."""
        store = brain["store"]

        m1 = store.add_memory("Bought ETH", "long_term", player_id="p1")
        m2 = store.add_memory("ETH went up 10%", "long_term", player_id="p1")
        m3 = store.add_memory("Sold ETH for profit", "long_term", player_id="p1")

        store.add_connection(m1, m2, "caused", 0.8)
        store.add_connection(m2, m3, "led_to", 0.9)

        conns = store.get_connections(m2)
        assert len(conns) == 2  # one incoming, one outgoing
