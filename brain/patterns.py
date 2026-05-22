"""PatternDetector: Analyzes trade memories to detect behavioural patterns."""
import json
from collections import Counter, defaultdict
from datetime import datetime
from brain.store import MemoryStore


class PatternDetector:
    def __init__(self, store: MemoryStore):
        self.store = store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_frequency(self, player_id: str = "default") -> dict:
        """Analyze trade frequency patterns.

        Returns:
            trades_per_day: dict mapping 'YYYY-MM-DD' -> count
            avg_trades_per_day: float
            most_active_day: str or None
            least_active_day: str or None
        """
        trades = self._get_trades(player_id)
        day_counts: Counter = Counter()
        for t in trades:
            ts = self._parse_timestamp(t)
            if ts:
                day_counts[ts.strftime("%Y-%m-%d")] += 1

        if not day_counts:
            return {
                "trades_per_day": {},
                "avg_trades_per_day": 0.0,
                "most_active_day": None,
                "least_active_day": None,
            }

        most_active = day_counts.most_common(1)[0][0]
        least_active = day_counts.most_common()[-1][0]

        return {
            "trades_per_day": dict(day_counts),
            "avg_trades_per_day": sum(day_counts.values()) / len(day_counts),
            "most_active_day": most_active,
            "least_active_day": least_active,
        }

    def analyze_timing(self, player_id: str = "default") -> dict:
        """Analyze when trades happen.

        Returns:
            trades_by_hour: dict 0-23 -> count
            trades_by_weekday: dict name -> count
            best_trading_hours: list[int] sorted by most trades
            worst_trading_hours: list[int]
        """
        trades = self._get_trades(player_id)
        hour_counts: Counter = Counter()
        weekday_counts: Counter = Counter()

        weekdays = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]

        for t in trades:
            ts = self._parse_timestamp(t)
            if ts:
                hour_counts[ts.hour] += 1
                weekday_counts[weekdays[ts.weekday()]] += 1

        # Fill missing hours with 0
        for h in range(24):
            hour_counts.setdefault(h, 0)

        sorted_hours = [h for h, _ in sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)]

        return {
            "trades_by_hour": dict(hour_counts),
            "trades_by_weekday": dict(weekday_counts),
            "best_trading_hours": sorted_hours[:5] if sorted_hours else [],
            "worst_trading_hours": sorted_hours[-5:] if sorted_hours else [],
        }

    def analyze_outcomes(self, player_id: str = "default") -> dict:
        """Analyze trade outcomes.

        Returns:
            total_trades, wins, losses, win_rate,
            avg_pnl, total_pnl, best_trade, worst_trade
        """
        trades = self._get_trades(player_id)
        total = 0
        wins = 0
        losses = 0
        pnls = []
        best_trade = None
        worst_trade = None

        for t in trades:
            outcome = t.get("tags", {}).get("outcome")
            if outcome is None:
                continue
            if isinstance(outcome, str):
                try:
                    outcome = json.loads(outcome)
                except (json.JSONDecodeError, TypeError):
                    continue

            total += 1
            pnl = outcome.get("pnl", 0)
            pnls.append(pnl)

            if outcome.get("success", False):
                wins += 1
            else:
                losses += 1

            record = {"memory_id": t["id"], "pnl": pnl, "trade": t}
            if best_trade is None or pnl > best_trade["pnl"]:
                best_trade = record
            if worst_trade is None or pnl < worst_trade["pnl"]:
                worst_trade = record

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / total if total else 0.0,
            "avg_pnl": sum(pnls) / len(pnls) if pnls else 0.0,
            "total_pnl": sum(pnls),
            "best_trade": best_trade,
            "worst_trade": worst_trade,
        }

    def detect_fomo(self, player_id: str = "default") -> dict:
        """Detect FOMO patterns — rapid successive trades.

        A "fomo streak" is consecutive trades within 10 minutes.

        Returns:
            fomo_events: int (number of streaks)
            avg_time_between_trades: float (minutes)
            longest_streak: int (number of trades in longest streak)
            streak_durations: list[int] (lengths of each streak)
        """
        trades = self._get_trades(player_id)
        timestamps = []
        for t in trades:
            ts = self._parse_timestamp(t)
            if ts:
                timestamps.append(ts)
        timestamps.sort()

        if len(timestamps) < 2:
            return {
                "fomo_events": 0,
                "avg_time_between_trades": 0.0,
                "longest_streak": len(timestamps),
                "streak_durations": [],
            }

        gaps = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60.0
            gaps.append(delta)

        avg_gap = sum(gaps) / len(gaps) if gaps else 0.0

        # Identify streaks: consecutive trades within 10 minutes
        streak_durations = []
        current_streak = 1
        for gap in gaps:
            if gap <= 10:
                current_streak += 1
            else:
                streak_durations.append(current_streak)
                current_streak = 1
        streak_durations.append(current_streak)

        fomo_events = sum(1 for s in streak_durations if s >= 3)
        longest = max(streak_durations) if streak_durations else 0

        return {
            "fomo_events": fomo_events,
            "avg_time_between_trades": avg_gap,
            "longest_streak": longest,
            "streak_durations": streak_durations,
        }

    def get_summary(self, player_id: str = "default") -> dict:
        """Get combined pattern summary."""
        return {
            "frequency": self.analyze_frequency(player_id),
            "timing": self.analyze_timing(player_id),
            "outcomes": self.analyze_outcomes(player_id),
            "fomo": self.detect_fomo(player_id),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_trades(self, player_id: str) -> list:
        """Fetch trade memories for a player."""
        return self.store.query_by_layer("short_term", player_id, limit=1000)

    @staticmethod
    def _parse_timestamp(trade: dict):
        """Extract a datetime from a trade memory's content."""
        content = trade.get("content", "")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                return None
        ts_str = content.get("timestamp") or trade.get("metadata", {}).get(
            "original_trade", {}
        ).get("timestamp")
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_timestamp_local(trade: dict):
        """Fallback: try to parse from the stored metadata."""
        return PatternDetector._parse_timestamp(trade)
