#!/usr/bin/env python3
"""
Agent Repairathy — Wellness Companion Prototype

Voice-first daily check-in system with mood tracking,
habit accountability, and emotional baseline monitoring.

Usage:
    python3 repairathy.py --checkin          — daily mood check-in
    python3 repairathy.py --mood-history     — show mood trends
    python3 repairathy.py --habits           — habit tracker
    python3 repairathy.py --journal "text"   — add journal entry
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(os.path.expanduser("~/.agent-repairathy"))
DATA_FILE = DATA_DIR / "data.json"

# ─── Mood Responses (voice scripts) ────────────────────────────────
MOOD_RESPONSES = {
    "low": [
        "I hear you. Tough days happen. But you showed up today — that counts.",
        "Rough one? That's okay. Tomorrow's a clean slate. Get some rest.",
        "Even Optimus Prime gets knocked down. What matters is getting back up.",
    ],
    "mid": [
        "Steady. Not great, not bad. That's progress — consistency beats perfection.",
        "You're holding it together. That takes strength. Keep going.",
        "Some days are just days. And that's perfectly fine.",
    ],
    "high": [
        "Now THAT'S what I'm talking about! Keep this energy rolling!",
        "Love to see it. You're glowing. Don't stop now!",
        "Optimus Prime would be proud. You're on fire today!",
    ],
}

HABIT_NUDGES = {
    "exercise": "Did you move your body today? Even 10 minutes counts.",
    "sleep": "How did you sleep? 7+ hours is the goal.",
    "meditation": "Did you take a moment to breathe today?",
    "water": "Have you been drinking water? Your body needs it.",
    "journal": "Write down one thing you're grateful for today.",
}

STREAK_MESSAGES = [
    "You've completed {habit} {streak} days in a row!",
    "Incredible — {streak} days of {habit}. You're building something real.",
    "{streak} days of {habit}. Optimus Prime approves.",
]


# ─── Data Management ───────────────────────────────────────────────
def load_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {
        "moods": [],
        "habits": {},
        "journal": [],
        "baseline": None,
        "created": datetime.now().isoformat(),
    }


def save_data(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2))


# ─── Mood Check-In ─────────────────────────────────────────────────
def checkin():
    data = load_data()

    print("\n🩺 Agent Repairathy — Daily Check-In\n")
    print("How are you feeling today?")
    print("  1-3:  😔 Struggling")
    print("  4-6:  😐 Steady")
    print("  7-10: 😊 Thriving\n")

    try:
        mood = int(input("Your mood (1-10): "))
        mood = max(1, min(10, mood))
    except (ValueError, EOFError):
        mood = 5
        print("(Defaulting to 5 — steady)")

    # Optional: what's on your mind?
    print()
    try:
        thought = input("What's on your mind? (optional, press Enter to skip): ").strip()
    except EOFError:
        thought = ""

    # Record mood
    entry = {
        "score": mood,
        "thought": thought,
        "timestamp": datetime.now().isoformat(),
    }
    data["moods"].append(entry)

    # Calculate baseline (7-day average)
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent = [m["score"] for m in data["moods"] if m["timestamp"] > week_ago]
    if recent:
        data["baseline"] = sum(recent) / len(recent)

    save_data(data)

    # Pick response
    if mood <= 3:
        tier = "low"
    elif mood <= 6:
        tier = "mid"
    else:
        tier = "high"

    import random
    response = random.choice(MOOD_RESPONSES[tier])
    print(f"\n💬 {response}")

    # Baseline comparison
    if data["baseline"] and len(recent) > 3:
        diff = mood - data["baseline"]
        if diff > 2:
            print(f"📈 That's above your 7-day average ({data['baseline']:.1f}). Nice!")
        elif diff < -2:
            print(f"📉 That's below your 7-day average ({data['baseline']:.1f}). Take it easy today.")
        else:
            print(f"📊 Right on your baseline ({data['baseline']:.1f}). Consistent.")

    print(f"\n✅ Check-in recorded. Mood: {mood}/10")


# ─── Mood History ──────────────────────────────────────────────────
def mood_history():
    data = load_data()
    moods = data.get("moods", [])

    if not moods:
        print("\n📊 No mood data yet. Start with --checkin")
        return

    print("\n📊 Agent Repairathy — Mood History\n")

    # Last 7 days
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent = [m for m in moods if m["timestamp"] > week_ago]

    if recent:
        scores = [m["score"] for m in recent]
        avg = sum(scores) / len(scores)
        print(f"  7-day average: {avg:.1f}/10")
        print(f"  Entries this week: {len(recent)}")
        print(f"  High: {max(scores)}/10 | Low: {min(scores)}/10")
        print()

        # Bar chart
        for entry in recent[-7:]:
            ts = datetime.fromisoformat(entry["timestamp"])
            bar = "█" * entry["score"] + "░" * (10 - entry["score"])
            print(f"  {ts.strftime('%m/%d')} {bar} {entry['score']}/10")

    # Baseline
    if data.get("baseline"):
        print(f"\n  Baseline (7-day avg): {data['baseline']:.1f}/10")

    # Streak
    if moods:
        streak = 0
        for m in reversed(moods):
            ts = datetime.fromisoformat(m["timestamp"])
            if ts.date() == (datetime.now() - timedelta(days=streak)).date():
                streak += 1
            else:
                break
        print(f"  Check-in streak: {streak} days")


# ─── Habit Tracker ─────────────────────────────────────────────────
def habits():
    data = load_data()
    if "habits" not in data:
        data["habits"] = {}

    print("\n🎯 Agent Repairathy — Habit Tracker\n")
    print("Current habits:")

    today = datetime.now().strftime("%Y-%m-%d")

    for habit, info in data.get("habits", {}).items():
        streak = info.get("streak", 0)
        done_today = today in info.get("completed", [])
        status = "✅" if done_today else "⬜"
        print(f"  {status} {habit} — {streak} day streak")

    if not data.get("habits"):
        print("  (none yet — add one below)")
        print()
        print("  Available nudges:")
        for habit, nudge in HABIT_NUDGES.items():
            print(f"    {habit}: {nudge}")

    print()
    try:
        action = input("Add habit, mark done, or Enter to skip: ").strip().lower()
    except EOFError:
        action = ""

    if action == "add":
        name = input("Habit name (exercise/sleep/meditation/water/journal/custom): ").strip().lower()
        if name:
            if name not in data["habits"]:
                data["habits"][name] = {"streak": 0, "completed": [], "nudge": HABIT_NUDGES.get(name, "")}
            save_data(data)
            print(f"✅ Added: {name}")
    elif action == "done":
        name = input("Which habit did you complete? ").strip().lower()
        if name in data.get("habits", {}):
            habit = data["habits"][name]
            if today not in habit.get("completed", []):
                habit.setdefault("completed", []).append(today)
                habit["streak"] = habit.get("streak", 0) + 1
                streak = habit["streak"]
                import random
                msg = random.choice(STREAK_MESSAGES).format(habit=name, streak=streak)
                print(f"🎉 {msg}")
                save_data(data)
            else:
                print(f"Already marked done today!")
        else:
            print(f"Habit '{name}' not found.")


# ─── Journal Entry ─────────────────────────────────────────────────
def journal(text=None):
    data = load_data()

    if not text:
        print("\n📝 Agent Repairathy — Journal\n")
        try:
            text = input("What's on your mind? ").strip()
        except EOFError:
            return

    if not text:
        return

    entry = {
        "text": text,
        "timestamp": datetime.now().isoformat(),
        "mood": data["moods"][-1]["score"] if data.get("moods") else None,
    }
    data.setdefault("journal", []).append(entry)
    save_data(data)

    print(f"\n✅ Journal entry recorded ({len(text)} words)")

    # Quick theme detection
    themes = []
    lower = text.lower()
    if any(w in lower for w in ["work", "job", "boss", "meeting"]):
        themes.append("work")
    if any(w in lower for w in ["tired", "exhausted", "sleep", "rest"]):
        themes.append("fatigue")
    if any(w in lower for w in ["happy", "great", "awesome", "love"]):
        themes.append("positive")
    if any(w in lower for w in ["stressed", "anxious", "worried", "nervous"]):
        themes.append("stress")
    if any(w in lower for w in ["exercise", "gym", "run", "walk"]):
        themes.append("fitness")

    if themes:
        print(f"🏷️  Themes detected: {', '.join(themes)}")


# ─── CLI ───────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Agent Repairathy — Wellness Companion")
    parser.add_argument("--checkin", action="store_true", help="Daily mood check-in")
    parser.add_argument("--mood-history", action="store_true", help="Show mood trends")
    parser.add_argument("--habits", action="store_true", help="Habit tracker")
    parser.add_argument("--journal", nargs="?", const="", help="Add journal entry")
    args = parser.parse_args()

    if args.checkin:
        checkin()
    elif args.mood_history:
        mood_history()
    elif args.habits:
        habits()
    elif args.journal is not None:
        journal(args.journal if args.journal else None)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
