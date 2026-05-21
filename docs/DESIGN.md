# AEG — Agent Economy Gaming

**Date:** 2026-05-21
**Status:** 🟡 Draft
**Repo:** github.com/ProtoJay4789/AEG

## Problem
Crypto/DeFi is intimidating. People ape into leverage without understanding liquidation mechanics, ignore risk signals, and lose real money. There's no safe way to learn DeFi intuition before going live.

## Proposed Solution
A trading simulation game where players start with spot trading capital, unlock leverage tiers through demonstrated skill, and face realistic liquidation mechanics — all without real money. Bot advisors teach by example: players who listen to them progress; players who ignore them get burned.

## Core Mechanics

### Trading Sim
- Start with base capital (spot trading only)
- Profitable trades build capital and reputation
- Reputation unlocks leverage tiers (1x → 5x → 10x → 20x)

### Leverage Unlock System
- Tier 1: 1x spot (everyone starts here)
- Tier 2: 2x-5x (unlocked at rep threshold)
- Tier 3: 10x (requires sustained performance)
- Tier 4: 20x (elite tier, high risk = high reward)

### Bot Advisors
- Bot advisors guide players through each tier
- Listening to bot advice = safer trades, better progression
- Ignoring bot advice = higher leverage unlocked faster BUT liquidation risk spikes
- Patience + bot interaction = steady progression
- Teaches real DeFi mechanics without real loss

### Gas Penalty System
- Bad trade → $0.50 fee added to your tab
- Unpaid = rep bleeds (-1 rep per day until paid)
- 7 days unpaid → fee doubles to $1.00
- 30 days → credit cap shrinks (can't borrow as much)
- "Parking ticket, not a boot" — you still play, you just owe money
- Rep decay creates urgency without rage quit

### Liquidation Mechanics
- Leverage positions have realistic liquidation thresholds
- Bot advisors warn before liquidation zone
- Getting liquidated = rep loss + cooldown period
- teaches "why liquidation is real" without losing real assets

## Architecture (Early Sketch)
- Frontend: Web-based trading UI (HTML/CSS/JS or React)
- Engine: Simulated market engine with realistic price feeds
- State: Player profile, rep, positions, debt ledger
- Advisors: Bot logic that reacts to player decisions

## Tech Stack
- TBD — likely web-based, could be on-chain for hackathon track

## Success Criteria
- Player can execute trades and see P&L
- Leverage tiers unlock based on reputation
- Bot advisors give contextual guidance
- Gas penalties accumulate and create real urgency
- Liquidation feels punishing but educational
