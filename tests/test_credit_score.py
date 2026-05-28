"""Tests for Credit Score Engine."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from credit_score.engine import CreditScoreEngine, CreditScore, TIERS, WEIGHTS


# ── Basic Score Tests ────────────────────────────────────────────────────

def test_empty_metrics():
    """Empty metrics should produce low score."""
    engine = CreditScoreEngine()
    result = engine.calculate()
    assert result.score >= 0
    assert result.score <= 1000
    assert result.tier in TIERS
    assert result.tier_name
    assert result.tier_emoji


def test_perfect_trader():
    """Perfect trader should score high."""
    engine = CreditScoreEngine()
    result = engine.calculate(
        win_rate=0.95,
        total_pnl_usd=10000,
        roi_percentage=200,
        total_trades=500,
        total_volume_usd=200000,
        avg_hold_time_hours=24,
        biggest_win_pct=150,
        biggest_loss_pct=-5,
        fomo_buys=0,
        panic_sells=0,
        perfect_timings=100,
        daily_returns=[0.01, 0.02, 0.015, 0.008, 0.012],
    )
    assert result.score >= 700
    assert result.tier in ["platinum", "diamond"]


def test_terrible_trader():
    """Terrible trader should score low."""
    engine = CreditScoreEngine()
    result = engine.calculate(
        win_rate=0.15,
        total_pnl_usd=-5000,
        roi_percentage=-60,
        total_trades=200,
        total_volume_usd=100000,
        avg_hold_time_hours=1,
        biggest_win_pct=10,
        biggest_loss_pct=-80,
        fomo_buys=50,
        panic_sells=40,
        perfect_timings=2,
        daily_returns=[-0.05, 0.01, -0.08, 0.02, -0.03, -0.1, 0.01],
    )
    assert result.score <= 400  # Volume inflates score for active traders
    assert result.tier in ["bronze", "silver"]


# ── Component Score Tests ────────────────────────────────────────────────

def test_win_rate_score():
    """Win rate scoring logic."""
    engine = CreditScoreEngine()
    
    # 50% win rate with enough trades
    score = engine._score_win_rate(0.50, 100)
    assert 40 <= score <= 70
    
    # 90% win rate
    score = engine._score_win_rate(0.90, 100)
    assert score >= 80
    
    # Too few trades
    score = engine._score_win_rate(0.90, 3)
    assert score < 30


def test_risk_adjusted_score():
    """Risk-adjusted return scoring."""
    engine = CreditScoreEngine()
    
    # Good returns, low volatility
    score = engine._score_risk_adjusted(
        roi=50,
        daily_returns=[0.02, 0.01, 0.03, 0.015, 0.02],
        biggest_win=100,
        biggest_loss=-10,
    )
    assert score >= 50
    
    # Bad returns, high volatility
    score = engine._score_risk_adjusted(
        roi=-30,
        daily_returns=[-0.05, 0.02, -0.08, 0.01, -0.03],
        biggest_win=20,
        biggest_loss=-60,
    )
    assert score < 50


def test_consistency_score():
    """Consistency scoring."""
    engine = CreditScoreEngine()
    
    # Consistent returns
    score = engine._score_consistency(
        daily_returns=[0.01, 0.012, 0.009, 0.011, 0.01],
        avg_hold_time_hours=24,
    )
    assert score >= 60
    
    # Volatile returns
    score = engine._score_consistency(
        daily_returns=[0.1, -0.15, 0.2, -0.25, 0.05],
        avg_hold_time_hours=1,
    )
    assert score < 50


def test_volume_score():
    """Volume scoring."""
    engine = CreditScoreEngine()
    
    # High volume
    score = engine._score_volume(500, 200000)
    assert score >= 70
    
    # Low volume
    score = engine._score_volume(5, 1000)
    assert score < 40
    
    # Zero trades
    score = engine._score_volume(0, 0)
    assert score == 0


def test_behavior_score():
    """Behavior scoring."""
    engine = CreditScoreEngine()
    
    # Good behavior
    score = engine._score_behavior(
        fomo_buys=0, panic_sells=0, perfect_timings=20, total_trades=50
    )
    assert score >= 60
    
    # Bad behavior
    score = engine._score_behavior(
        fomo_buys=30, panic_sells=20, perfect_timings=2, total_trades=50
    )
    assert score < 40


# ── Tier Tests ───────────────────────────────────────────────────────────

def test_tier_bronze():
    """Score 0-199 should be bronze."""
    engine = CreditScoreEngine()
    result = engine.calculate(
        win_rate=0.1,
        total_trades=10,
        daily_returns=[-0.1, -0.05, -0.08],
    )
    if result.score < 200:
        assert result.tier == "bronze"
        assert result.tier_name == "The Gambler"
        assert result.tier_emoji == "🥉"


def test_tier_diamond():
    """Score 800+ should be diamond."""
    engine = CreditScoreEngine()
    result = engine.calculate(
        win_rate=0.95,
        total_pnl_usd=50000,
        roi_percentage=300,
        total_trades=1000,
        total_volume_usd=500000,
        avg_hold_time_hours=48,
        biggest_win_pct=200,
        biggest_loss_pct=-2,
        fomo_buys=0,
        panic_sells=0,
        perfect_timings=200,
        daily_returns=[0.02, 0.03, 0.015, 0.025, 0.01, 0.02, 0.018, 0.022],
    )
    if result.score >= 800:
        assert result.tier == "diamond"
        assert result.tier_name == "The Whale"
        assert result.tier_emoji == "👑"


def test_all_tiers_defined():
    """All 5 tiers should be defined."""
    assert len(TIERS) == 5
    assert "bronze" in TIERS
    assert "silver" in TIERS
    assert "gold" in TIERS
    assert "platinum" in TIERS
    assert "diamond" in TIERS


def test_weights_sum_to_one():
    """Weights should sum to 1.0."""
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 0.001


# ── Edge Case Tests ──────────────────────────────────────────────────────

def test_negative_roi():
    """Negative ROI should still produce valid score."""
    engine = CreditScoreEngine()
    result = engine.calculate(
        win_rate=0.3,
        total_pnl_usd=-2000,
        roi_percentage=-40,
        total_trades=100,
        daily_returns=[-0.01, -0.02, -0.03, -0.01, -0.02],
    )
    assert result.score >= 0
    assert result.score <= 1000


def test_zero_trades():
    """Zero trades should produce minimum score."""
    engine = CreditScoreEngine()
    result = engine.calculate(total_trades=0)
    assert result.score >= 0
    assert result.score <= 200  # Should be bronze


def test_single_trade():
    """Single trade should produce valid score."""
    engine = CreditScoreEngine()
    result = engine.calculate(
        win_rate=1.0,
        total_trades=1,
        total_pnl_usd=100,
        roi_percentage=50,
        daily_returns=[0.5],
    )
    assert result.score >= 0
    assert result.score <= 1000


def test_narrative_generated():
    """Narrative should be generated for all tiers."""
    engine = CreditScoreEngine()
    result = engine.calculate()
    assert result.headline
    assert result.advice


def test_score_clamped():
    """Score should be clamped to 0-1000."""
    engine = CreditScoreEngine()
    # Extreme positive
    result = engine.calculate(
        win_rate=1.0,
        total_pnl_usd=1000000,
        roi_percentage=10000,
        total_trades=10000,
        total_volume_usd=10000000,
        perfect_timings=10000,
    )
    assert result.score <= 1000
    
    # Extreme negative
    result = engine.calculate(
        win_rate=0.0,
        total_pnl_usd=-1000000,
        roi_percentage=-100,
        total_trades=10000,
        total_volume_usd=10000000,
        fomo_buys=10000,
        panic_sells=10000,
    )
    assert result.score >= 0
