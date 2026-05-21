# AEG Phase 1 — Build Plan

**Created:** 2026-05-21
**Status:** 🟢 Active
**Goal:** MVP trading sim with spot trading, rep system, leverage tiers, bot advisors, gas penalties

## Task List

### Task 1: Market Engine (`js/engine/market.js`)
- Random walk price generation with mean reversion
- Configurable volatility, tick interval
- Price history array for chart rendering
- Event emitter for price updates
- **Verify:** Unit test — price stays within bounds, history grows

### Task 2: Portfolio Engine (`js/engine/portfolio.js`)
- Player state: capital, positions[], tradeHistory[], reputation, gasDebt
- Buy/sell execution at market price
- P&L calculation (unrealized + realized)
- Position tracking with entry price, quantity, unrealized P&L
- **Verify:** Unit test — buy increases position, sell decreases, P&L correct

### Task 3: Reputation System (`js/engine/rep.js`)
- Rep starts at 0
- Profitable trade: +rep based on P&L magnitude
- Losing trade: -rep based on loss magnitude
- Rep thresholds for leverage tiers (0/50/150/400)
- Rep decay from unpaid gas debt (-1/day)
- **Verify:** Unit test — rep changes correctly, tier unlocks at thresholds

### Task 4: Gas Penalty System (`js/engine/penalty.js`)
- Bad trade detection (loss beyond threshold)
- Fee accumulation ($0.50 base)
- Unpaid tracking with day counter
- Auto-doubling at 7 days
- Credit cap reduction at 30 days
- **Verify:** Unit test — fees accumulate, double at 7 days, cap shrinks at 30

### Task 5: Bot Advisor (`js/bots/advisor.js`)
- Market condition analysis (trend, volatility, risk)
- Trade recommendation generation
- Advice tracking (followed/ignored)
- Escalating guidance based on player behavior
- **Verify:** Unit test — gives advice, tracks follow/ignore

### Task 6: UI Shell (`index.html`, `css/style.css`)
- Trading dashboard layout
- Price chart area
- Portfolio panel (capital, positions, P&L)
- Trade panel (buy/sell buttons, amount input)
- Rep/leverage tier display
- Bot advisor chat area
- Gas debt display
- **Verify:** Visual — loads in browser, responsive layout

### Task 7: Price Chart (`js/ui/chart.js`)
- Canvas-based line chart
- Real-time price updates
- Candlestick or line visualization
- Volume bars (optional)
- **Verify:** Visual — chart updates with market ticks

### Task 8: App Controller (`js/ui/app.js`)
- Wire market engine to UI
- Wire portfolio engine to UI
- Wire bot advisor to UI
- Event-driven updates (price tick → chart update → portfolio recalc)
- localStorage persistence
- **Verify:** Integration — full loop works in browser

### Task 9: Onboarding Flow
- Welcome screen with tutorial
- Starting capital display ($10,000)
- First trade guided by bot advisor
- **Verify:** New player can start and make first trade

## Execution Order
1. Tasks 1-3 (engine layer) — parallel subagents
2. Tasks 4-5 (game mechanics) — sequential after engine
3. Tasks 6-7 (UI) — parallel with engine refinement
4. Tasks 8-9 (integration + onboarding) — after all pieces exist

## Anti-YAGNI Check
- ✅ No React (vanilla JS is enough)
- ✅ No backend (localStorage for state)
- ✅ No on-chain (Phase 3)
- ✅ No multiplayer (Phase 2)
- ✅ No voice (Phase 2)
- ❌ Building beyond the plan → STOP
