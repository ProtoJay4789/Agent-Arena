"""Tests for PatternDetector."""
import json
import pytest
from datetime import datetime, timedelta
from brain.store import MemoryStore
from brain.tagger import TradeTagger
from brain.patterns import PatternDetector


@pytest.fixture
def store():
    return MemoryStore(db_path=":memory:")


@pytest.fixture
def tagger(store):
    return TradeTagger(store)


@pytest.fixture
def detector(store):
    return PatternDetector(store)


def _seed_trades(tagger, count=5, player_id="test", base_time=None):
    """Helper: store a series of trades with varying data."""
    if base_time is None:
        base_time = datetime(2026, 5, 1, 10, 0, 0)

    ids = []
    tokens = ["SOL", "ETH", "BTC", "DOGE", "AVAX", "LINK", "MATIC"]
    for i in range(count):
        ts = base_time + timedelta(hours=i)
        trade = {
            "action": "buy" if i % 2 == 0 else "sell",
            "token": tokens[i % len(tokens)],
            "amount": 10 + i * 5,
            "price": 100 + i * 10,
            "price_1h_ago": 100 + (i - 1) * 10 if i > 0 else 100,
            "timestamp": ts.isoformat(),
            "player_id": player_id,
        }
        tagged = tagger.tag_trade(trade)
        mid = tagger.store_trade(tagged)

        # Resolve some trades with outcomes
        if i % 2 == 1:
            success = i % 4 == 1
            pnl = 50.0 * i if success else -30.0 * i
            tagger.resolve_trade(mid, {
                "pnl": pnl,
                "duration_minutes": 10 + i * 5,
                "success": success,
            })
        ids.append(mid)
    return ids


# ------------------------------------------------------------------
# analyze_frequency
# ------------------------------------------------------------------

def test_analyze_frequency(tagger, detector):
    """Frequency analysis across multiple days."""
    base = datetime(2026, 5, 1, 10, 0, 0)
    # 2 trades on day 1, 3 on day 2
    for i in range(2):
        ts = base + timedelta(hours=i)
        trade = {
            "action": "buy", "token": "SOL", "amount": 10,
            "price": 100, "price_1h_ago": 100,
            "timestamp": ts.isoformat(), "player_id": "freq_test",
        }
        tagger.store_trade(tagger.tag_trade(trade))

    for i in range(3):
        ts = base + timedelta(days=1, hours=i)
        trade = {
            "action": "sell", "token": "ETH", "amount": 20,
            "price": 2000, "price_1h_ago": 2000,
            "timestamp": ts.isoformat(), "player_id": "freq_test",
        }
        tagger.store_trade(tagger.tag_trade(trade))

    result = detector.analyze_frequency("freq_test")
    assert len(result["trades_per_day"]) == 2
    assert result["avg_trades_per_day"] == 2.5
    assert result["most_active_day"] == "2026-05-02"
    assert result["least_active_day"] == "2026-05-01"


# ------------------------------------------------------------------
# analyze_timing
# ------------------------------------------------------------------

def test_analyze_timing(tagger, detector):
    """Timing analysis with trades at different hours."""
    base = datetime(2026, 5, 4, 0, 0, 0)  # Monday
    hours = [9, 14, 21, 9, 14]  # two at 9, two at 14, one at 21
    for i, h in enumerate(hours):
        ts = base + timedelta(hours=h)
        trade = {
            "action": "buy", "token": "SOL", "amount": 10,
            "price": 100, "price_1h_ago": 100,
            "timestamp": ts.isoformat(), "player_id": "time_test",
        }
        tagger.store_trade(tagger.tag_trade(trade))

    result = detector.analyze_timing("time_test")
    assert result["trades_by_hour"][9] == 2
    assert result["trades_by_hour"][14] == 2
    assert result["trades_by_hour"][21] == 1
    assert "Monday" in result["trades_by_weekday"]
    assert result["trades_by_weekday"]["Monday"] == 5
    # Best hours should include 9 and 14
    assert 9 in result["best_trading_hours"]
    assert 14 in result["best_trading_hours"]


# ------------------------------------------------------------------
# analyze_outcomes
# ------------------------------------------------------------------

def test_analyze_outcomes(tagger, detector):
    """Outcome analysis with mix of wins and losses."""
    _seed_trades(tagger, count=5, player_id="outcome_test")
    result = detector.analyze_outcomes("outcome_test")

    # We resolved indices 1 and 3 (odd), so total_trades == 2
    assert result["total_trades"] == 2
    assert result["wins"] + result["losses"] == 2
    assert 0.0 <= result["win_rate"] <= 1.0
    assert result["best_trade"] is not None
    assert result["worst_trade"] is not None
    assert result["best_trade"]["pnl"] >= result["worst_trade"]["pnl"]


# ------------------------------------------------------------------
# detect_fomo
# ------------------------------------------------------------------

def test_detect_fomo(tagger, detector):
    """FOMO detection with rapid trades."""
    base = datetime(2026, 5, 1, 12, 0, 0)
    # 5 trades within 5 minutes each → streak of 5
    for i in range(5):
        ts = base + timedelta(minutes=i * 3)
        trade = {
            "action": "buy", "token": "SOL", "amount": 10,
            "price": 100, "price_1h_ago": 100,
            "timestamp": ts.isoformat(), "player_id": "fomo_test",
        }
        tagger.store_trade(tagger.tag_trade(trade))

    # One trade far away
    far_ts = base + timedelta(hours=2)
    trade = {
        "action": "sell", "token": "ETH", "amount": 20,
        "price": 2000, "price_1h_ago": 2000,
        "timestamp": far_ts.isoformat(), "player_id": "fomo_test",
    }
    tagger.store_trade(tagger.tag_trade(trade))

    result = detector.detect_fomo("fomo_test")
    assert result["longest_streak"] >= 5
    assert result["fomo_events"] >= 1  # streak of 5 >= 3
    assert len(result["streak_durations"]) >= 2


# ------------------------------------------------------------------
# get_summary
# ------------------------------------------------------------------

def test_get_summary(tagger, detector):
    """Summary combines all analyses."""
    _seed_trades(tagger, count=5, player_id="summary_test")
    result = detector.get_summary("summary_test")
    assert "frequency" in result
    assert "timing" in result
    assert "outcomes" in result
    assert "fomo" in result
    assert result["frequency"]["avg_trades_per_day"] > 0
    assert result["outcomes"]["total_trades"] >= 0


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------

def test_empty_store(detector):
    """All analyses work on an empty store."""
    freq = detector.analyze_frequency("empty")
    assert freq["trades_per_day"] == {}
    assert freq["avg_trades_per_day"] == 0.0
    assert freq["most_active_day"] is None

    timing = detector.analyze_timing("empty")
    assert sum(timing["trades_by_hour"].values()) == 0

    outcomes = detector.analyze_outcomes("empty")
    assert outcomes["total_trades"] == 0
    assert outcomes["win_rate"] == 0.0

    fomo = detector.detect_fomo("empty")
    assert fomo["fomo_events"] == 0

    summary = detector.get_summary("empty")
    assert isinstance(summary, dict)
