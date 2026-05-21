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

## Layer Integrations (Brainstorm)

### 1. AAE Credit Layer ↔ AEG Reputation
Real-world agent performance data feeds into AEG reputation. Agents that perform well in live DeFi (AAE) get reputation bonuses in the game. Creates a feedback loop: game teaches skills → skills apply to real agents → real performance boosts game standing.

### 2. DeFi Signal Agent ↔ Market Events
The signal agent's real-time alerts (whale movements, unusual volume, protocol changes) become in-game market events. Players react to the same signals real traders face. Bridges simulation and reality.

### 3. Rugcheck ↔ Scam Detection Training
Token launch monitoring feeds "rug alert" events into the game. Players learn to spot honeypots, rug pulls, and sketchy contracts by interacting with real monitoring data. Educational layer that ties into the security mission.

### 4. x402 Payments ↔ In-Game Economy
Microtransactions for premium features: custom bot advisors, advanced charting, cosmetic portfolio themes. Also enables agent-to-agent commerce within the game economy.

### 5. Voice Bot Advisors
Using speech engine for immersive, personality-driven bot guidance. Different advisor voices for different strategies (conservative, aggressive, degen). Makes the learning experience more engaging.

### 6. Multiplayer & Competitive
Leaderboards, head-to-head trading matches, guild systems. Players compete for reputation rankings. Social layer that drives retention.

### 7. NFT Achievements
Trading milestones minted as on-chain NFTs. "First 10x leverage trade," "Survived a flash crash," "100 trades without liquidation." Collectible progression system.

### 8. Cross-Chain Simulation
Using browser cloaking infrastructure to simulate trading across different chains. Each chain has different fee structures, liquidity profiles, and risk characteristics. Teaches chain-specific DeFi mechanics.

### 9. AEG as Agent Training Ground
The ultimate loop: AEG-trained agents feed back into real DeFi operations. The game becomes a testing ground for real agent strategies. Players develop strategies → agents execute them in production → performance data feeds back into the game.

## Architecture
- Frontend: Web-based trading UI (vanilla HTML/CSS/JS, Phase 1)
- Engine: Simulated market engine with random walk price generation
- State: Player profile, rep, positions, debt ledger (localStorage)
- Advisors: Bot logic that reacts to player decisions
- Future: On-chain state for hackathon track, multiplayer backend

## Tech Stack
- Phase 1: Vanilla HTML/CSS/JS (fast MVP)
- Phase 2: React or Next.js (if complexity warrants)
- Phase 3: Solidity contracts for on-chain state (hackathon submission)

## Success Criteria
- Player can execute spot trades and see P&L
- Leverage tiers unlock based on reputation
- Bot advisors give contextual guidance
- Gas penalties accumulate and create real urgency
- Liquidation feels punishing but educational
- Layer integrations are architecturally viable (Phase 2+)
