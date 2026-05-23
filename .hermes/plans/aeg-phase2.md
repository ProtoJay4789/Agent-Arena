# AEG Phase 2 — Build Plan

**Date:** 2026-05-23
**Status:** 🟢 In Progress
**Repo:** /root/AEG (existing Phase 1)

## What Phase 1 Has
- Market Engine (random walk, mean reversion)
- Portfolio Engine (buy/sell, P&L, positions)
- Reputation System (rep tiers, thresholds)
- Gas Penalty System (fees, auto-doubling)
- Bot Advisor (basic trade recommendations)
- UI Shell (dashboard, chart, trade panel)
- 53/53 smoke tests passing

## What Phase 2 Adds

### 1. Leverage Mechanics (`js/engine/leverage.js`)
- Margin trading: 2x, 5x, 10x leverage tiers
- Liquidation engine: auto-close positions at margin threshold
- Margin call warnings (bot advisor alerts)
- Leverage unlocked by rep tier:
  - Rep 0-49: Spot only (1x)
  - Rep 50-149: 2x leverage
  - Rep 150-399: 5x leverage
  - Rep 400+: 10x leverage
- Interest on margin positions (hourly accrual)
- **Verify:** Unit test — leverage calculation, liquidation trigger, margin call

### 2. Advanced Bots (`js/bots/`)
- **MomentumBot** (`momentum.js`): Follows trends, buys when price rising, sells when falling
- **ContrarianBot** (`contrarian.js`): Does opposite — buys dips, sells peaks
- **WhaleBot** (`whale.js`): Simulates whale movements, manipulates price briefly
- Each bot has personality, risk tolerance, capital allocation
- Bot vs Player: bots compete for same opportunities
- **Verify:** Each bot has distinct behavior, trades independently

### 3. Simulated Multiplayer (`js/engine/multiplayer.js`)
- 5-10 AI opponents trading in the same market
- Each opponent has unique strategy (aggressive, conservative, sniper, holder)
- Leaderboard showing top traders by P&L
- "Market events" that affect all players simultaneously
- Gas competition: more players = higher gas fees
- **Verify:** Leaderboard updates, opponents trade, events fire

### 4. Voice Integration (`js/ui/voice.js`)
- Bot advisor speaks key alerts via Web Speech API
- Liquidation warning voice
- New trade confirmation voice
- Leaderboard position voice
- Toggle on/off in settings
- **Verify:** Voice fires on key events

### 5. UI Enhancements
- Leverage selector in trade panel
- Margin indicator (current margin, liquidation price)
- Leaderboard sidebar
- Bot activity feed (shows what bots are doing)
- Market events banner
- Settings panel (voice toggle, speed)
- **Verify:** All new UI elements render correctly

## Files to Create/Modify
- `js/engine/leverage.js` — NEW
- `js/engine/multiplayer.js` — NEW
- `js/bots/momentum.js` — NEW
- `js/bots/contrarian.js` — NEW
- `js/bots/whale.js` — NEW
- `js/ui/voice.js` — NEW
- `js/ui/app.js` — MODIFY (wire new systems)
- `js/ui/dashboard.js` — MODIFY (leverage + leaderboard UI)
- `index.html` — MODIFY (new UI elements)
- `smoke_test.js` — EXTEND (new tests for Phase 2)

## Verification
- All existing 53 smoke tests still pass
- New tests for leverage, multiplayer, advanced bots
- Full game loop: trade → leverage → liquidation → leaderboard update → voice alert
