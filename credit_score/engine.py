"""
Credit Score Engine — Composite scoring for AI trading agents.

Calculates a 0-1000 credit score based on:
- Win rate (30%)
- Risk-adjusted returns (25%)
- Consistency (20%)
- Volume & activity (15%)
- Behavior (10%)

Tiers:
- 0-199:   Bronze    — "The Gambler"
- 200-399: Silver    — "The Learner"
- 400-599: Gold      — "The Trader"
- 600-799: Platinum  — "The Strategist"
- 800-1000: Diamond  — "The Whale"
"""

from dataclasses import dataclass, field
from typing import Optional
import math


# ── Tier Definitions ─────────────────────────────────────────────────────

TIERS = {
    "bronze":   {"min": 0,   "max": 199,  "name": "The Gambler",     "emoji": "🥉"},
    "silver":   {"min": 200, "max": 399,  "name": "The Learner",     "emoji": "🥈"},
    "gold":     {"min": 400, "max": 599,  "name": "The Trader",      "emoji": "🥇"},
    "platinum": {"min": 600, "max": 799,  "name": "The Strategist",  "emoji": "💎"},
    "diamond":  {"min": 800, "max": 1000, "name": "The Whale",       "emoji": "👑"},
}

# Score weights
WEIGHTS = {
    "win_rate": 0.30,
    "risk_adjusted_return": 0.25,
    "consistency": 0.20,
    "volume": 0.15,
    "behavior": 0.10,
}


# ── Data Classes ─────────────────────────────────────────────────────────

@dataclass
class CreditScore:
    """Complete credit score result."""
    score: int                     # 0-1000
    tier: str                      # bronze, silver, gold, platinum, diamond
    tier_name: str                 # The Gambler, The Learner, etc.
    tier_emoji: str                # 🥉, 🥈, 🥇, 💎, 👑
    
    # Component scores (0-100 each)
    win_rate_score: float = 0.0
    risk_adjusted_score: float = 0.0
    consistency_score: float = 0.0
    volume_score: float = 0.0
    behavior_score: float = 0.0
    
    # Metadata
    total_trades: int = 0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    roi_percentage: float = 0.0
    max_drawdown: float = 0.0
    
    # Narrative
    headline: str = ""
    advice: str = ""


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of how the score was calculated."""
    raw_metrics: dict = field(default_factory=dict)
    normalized_scores: dict = field(default_factory=dict)
    weighted_scores: dict = field(default_factory=dict)
    total_score: float = 0.0


# ── Scoring Engine ───────────────────────────────────────────────────────

class CreditScoreEngine:
    """
    Calculates credit scores for trading agents.
    
    Usage:
        engine = CreditScoreEngine()
        result = engine.calculate(
            win_rate=0.65,
            total_pnl_usd=1500.0,
            roi_percentage=45.0,
            total_trades=120,
            total_volume_usd=50000.0,
            avg_hold_time_hours=12.0,
            biggest_win_pct=120.0,
            biggest_loss_pct=-35.0,
            fomo_buys=3,
            panic_sells=5,
            perfect_timings=8,
            daily_returns=[0.02, -0.01, 0.03, -0.02, 0.01],
        )
    """
    
    def calculate(
        self,
        win_rate: float = 0.0,
        total_pnl_usd: float = 0.0,
        roi_percentage: float = 0.0,
        total_trades: int = 0,
        total_volume_usd: float = 0.0,
        avg_hold_time_hours: float = 0.0,
        biggest_win_pct: float = 0.0,
        biggest_loss_pct: float = 0.0,
        fomo_buys: int = 0,
        panic_sells: int = 0,
        perfect_timings: int = 0,
        daily_returns: Optional[list] = None,
        **kwargs,
    ) -> CreditScore:
        """Calculate credit score from trading metrics."""
        
        if daily_returns is None:
            daily_returns = []
        
        # Calculate component scores
        win_rate_score = self._score_win_rate(win_rate, total_trades)
        risk_adjusted_score = self._score_risk_adjusted(
            roi_percentage, daily_returns, biggest_win_pct, biggest_loss_pct
        )
        consistency_score = self._score_consistency(daily_returns, avg_hold_time_hours)
        volume_score = self._score_volume(total_trades, total_volume_usd)
        behavior_score = self._score_behavior(
            fomo_buys, panic_sells, perfect_timings, total_trades
        )
        
        # Weighted total (scale 0-100 → 0-1000)
        total_score = (
            win_rate_score * WEIGHTS["win_rate"] +
            risk_adjusted_score * WEIGHTS["risk_adjusted_return"] +
            consistency_score * WEIGHTS["consistency"] +
            volume_score * WEIGHTS["volume"] +
            behavior_score * WEIGHTS["behavior"]
        ) * 10  # Scale to 0-1000
        
        # Clamp to 0-1000
        total_score = max(0, min(1000, total_score))
        
        # Determine tier
        tier, tier_name, tier_emoji = self._get_tier(total_score)
        
        # Calculate Sharpe ratio for metadata
        sharpe = self._sharpe_ratio(daily_returns) if daily_returns else 0.0
        
        # Calculate max drawdown
        max_dd = self._max_drawdown(daily_returns) if daily_returns else 0.0
        
        # Generate narrative
        headline, advice = self._generate_narrative(
            tier, win_rate, roi_percentage, total_trades
        )
        
        return CreditScore(
            score=int(total_score),
            tier=tier,
            tier_name=tier_name,
            tier_emoji=tier_emoji,
            win_rate_score=win_rate_score,
            risk_adjusted_score=risk_adjusted_score,
            consistency_score=consistency_score,
            volume_score=volume_score,
            behavior_score=behavior_score,
            total_trades=total_trades,
            win_rate=win_rate,
            sharpe_ratio=sharpe,
            roi_percentage=roi_percentage,
            max_drawdown=max_dd,
            headline=headline,
            advice=advice,
        )
    
    # ── Component Scorers ────────────────────────────────────────────────
    
    def _score_win_rate(self, win_rate: float, total_trades: int) -> float:
        """Score win rate (0-100)."""
        if total_trades < 5:
            return 20.0  # Too few trades to judge
        
        # Win rate directly maps to score, with bonus for high volume
        base = win_rate * 100
        
        # Volume bonus: +10 for 100+ trades, +20 for 500+
        if total_trades >= 500:
            base += 20
        elif total_trades >= 100:
            base += 10
        
        return min(100, base)
    
    def _score_risk_adjusted(
        self,
        roi: float,
        daily_returns: list,
        biggest_win: float,
        biggest_loss: float,
    ) -> float:
        """Score risk-adjusted returns (0-100)."""
        if not daily_returns and roi == 0:
            return 10.0  # No data
        
        # Sharpe ratio component
        sharpe = self._sharpe_ratio(daily_returns) if daily_returns else 0
        sharpe_score = min(50, max(0, (sharpe + 1) * 25))  # -1 to +1 → 0 to 50
        
        # ROI component (capped)
        roi_score = min(30, max(0, roi * 0.3))  # Up to 100% ROI = 30 points
        
        # Risk management (penalize big drawdowns)
        risk_penalty = 0
        if biggest_loss < -50:
            risk_penalty = 20
        elif biggest_loss < -30:
            risk_penalty = 10
        
        return min(100, sharpe_score + roi_score - risk_penalty + 20)
    
    def _score_consistency(self, daily_returns: list, avg_hold_time_hours: float) -> float:
        """Score consistency of returns (0-100)."""
        if len(daily_returns) < 3:
            return 30.0  # Not enough data
        
        # Standard deviation of returns (lower = more consistent)
        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = math.sqrt(variance)
        
        # Lower std dev = higher score
        consistency = max(0, 100 - (std_dev * 1000))
        
        # Bonus for consistent trading (not too sporadic)
        if avg_hold_time_hours > 0 and avg_hold_time_hours < 168:  # 1 week
            consistency += 10
        
        return min(100, consistency)
    
    def _score_volume(self, total_trades: int, total_volume: float) -> float:
        """Score trading volume (0-100)."""
        # Trade count score (logarithmic)
        if total_trades <= 0:
            return 0
        
        trade_score = min(50, math.log10(total_trades + 1) * 15)
        
        # Volume score (logarithmic)
        if total_volume <= 0:
            volume_score = 0
        else:
            volume_score = min(50, math.log10(total_volume + 1) * 7)
        
        return min(100, trade_score + volume_score)
    
    def _score_behavior(
        self,
        fomo_buys: int,
        panic_sells: int,
        perfect_timings: int,
        total_trades: int,
    ) -> float:
        """Score trading behavior (0-100)."""
        if total_trades == 0:
            return 20.0
        
        # Start at 60 (neutral)
        score = 60.0
        
        # Bonus for good behavior
        good_ratio = perfect_timings / total_trades if total_trades > 0 else 0
        score += good_ratio * 40  # Up to +40 for perfect timing
        
        # Penalty for bad behavior
        bad_count = fomo_buys + panic_sells
        bad_ratio = bad_count / total_trades if total_trades > 0 else 0
        score -= bad_ratio * 60  # Up to -60 for bad behavior
        
        return max(0, min(100, score))
    
    # ── Helpers ──────────────────────────────────────────────────────────
    
    def _sharpe_ratio(self, returns: list, risk_free_rate: float = 0.0) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance) if variance > 0 else 0.001
        
        excess_return = mean - risk_free_rate
        # Annualize (assume daily returns, 365 trading days)
        annualized_excess = excess_return * 365
        annualized_std = std_dev * math.sqrt(365)
        
        return annualized_excess / annualized_std if annualized_std > 0 else 0.0
    
    def _max_drawdown(self, returns: list) -> float:
        """Calculate maximum drawdown from daily returns."""
        if not returns:
            return 0.0
        
        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0
        
        for r in returns:
            cumulative *= (1 + r)
            peak = max(peak, cumulative)
            drawdown = (peak - cumulative) / peak
            max_dd = max(max_dd, drawdown)
        
        return max_dd * 100  # Return as percentage
    
    def _get_tier(self, score: float) -> tuple:
        """Determine tier from score."""
        score = int(score)
        for tier_name, tier_info in TIERS.items():
            if tier_info["min"] <= score <= tier_info["max"]:
                return tier_name, tier_info["name"], tier_info["emoji"]
        return "bronze", "The Gambler", "🥉"
    
    def _generate_narrative(
        self, tier: str, win_rate: float, roi: float, total_trades: int
    ) -> tuple:
        """Generate headline and advice based on score."""
        headlines = {
            "bronze": "You're gambling, not trading.",
            "silver": "You're learning. Slowly.",
            "gold": "You've got skills. Now refine them.",
            "platinum": "Strategy is your middle name.",
            "diamond": "The market bends to your will.",
        }
        
        advice_map = {
            "bronze": "Stop trading immediately. Paper trade for 3 months.",
            "silver": "Focus on risk management. Cut losses faster.",
            "gold": "You're profitable. Now optimize for consistency.",
            "platinum": "Sharpen your edge. The next level is within reach.",
            "diamond": "Teach others. Your track record speaks volumes.",
        }
        
        return headlines.get(tier, "Keep grinding."), advice_map.get(tier, "Stay focused.")


# ── Quick test ───────────────────────────────────────────────────────────

def _test():
    """Quick test of the credit score engine."""
    engine = CreditScoreEngine()
    
    # Test: mediocre trader
    result = engine.calculate(
        win_rate=0.45,
        total_pnl_usd=-500,
        roi_percentage=-15,
        total_trades=80,
        total_volume_usd=25000,
        avg_hold_time_hours=6,
        biggest_win_pct=45,
        biggest_loss_pct=-25,
        fomo_buys=12,
        panic_sells=8,
        perfect_timings=5,
        daily_returns=[0.02, -0.03, 0.01, -0.04, 0.03, -0.01, 0.02, -0.02],
    )
    
    print(f"{'='*50}")
    print(f"CREDIT SCORE: {result.tier_emoji} {result.score}/1000")
    print(f"TIER: {result.tier_name} ({result.tier})")
    print(f"{'='*50}")
    print(f"Win Rate:      {result.win_rate_score:.0f}/100")
    print(f"Risk-Adjusted: {result.risk_adjusted_score:.0f}/100")
    print(f"Consistency:   {result.consistency_score:.0f}/100")
    print(f"Volume:        {result.volume_score:.0f}/100")
    print(f"Behavior:      {result.behavior_score:.0f}/100")
    print(f"{'='*50}")
    print(f"Sharpe Ratio:  {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown:  {result.max_drawdown:.1f}%")
    print(f"{'='*50}")
    print(f"💡 {result.headline}")
    print(f"📋 {result.advice}")
    
    return result


if __name__ == "__main__":
    _test()
