/**
 * Smoke test for AEG core engine modules.
 * Run: node --experimental-vm-modules smoke_test.js
 * Or simply: node smoke_test.js (ES modules)
 */

import { MarketEngine } from './js/engine/market.js';
import { Portfolio } from './js/engine/portfolio.js';
import { ReputationManager } from './js/engine/rep.js';
import { GasPenaltyManager } from './js/engine/penalty.js';
import { BotAdvisor } from './js/bots/advisor.js';

let passed = 0;
let failed = 0;

function assert(condition, label) {
  if (condition) {
    console.log(`  ✅ ${label}`);
    passed++;
  } else {
    console.log(`  ❌ ${label}`);
    failed++;
  }
}

// ─── MarketEngine ───
console.log('\n📈 MarketEngine');
const market = new MarketEngine({ initialPrice: 100, tickInterval: 500 });
assert(market.getCurrentPrice() === 100, 'Initial price is 100');
assert(market.getPriceHistory().length === 1, 'History has 1 entry (initial)');

// Manual tick
const tick = market.manualTick();
assert(typeof tick.price === 'number', 'Tick returns a price');
assert(tick.price > 0, 'Price is positive after tick');
assert(market.getPriceHistory().length === 2, 'History grew to 2');
assert(market.getTickCount() === 1, 'Tick count is 1');

// Subscribe
let notified = false;
const unsub = market.subscribe(() => { notified = true; });
market.manualTick();
assert(notified, 'Subscriber was notified');
unsub();

// Start/Stop
market.start();
assert(market.isRunning(), 'Market is running');
market.stop();
assert(!market.isRunning(), 'Market stopped');

// ─── Portfolio ───
console.log('\n💼 Portfolio');
const portfolio = new Portfolio(10000);
assert(portfolio.getCapital() === 10000, 'Starting capital is 10000');

// Buy
const pos = portfolio.buy(100, 10);
assert(pos.entryPrice === 100, 'Position entry price is 100');
assert(pos.quantity === 10, 'Position quantity is 10');
assert(portfolio.getCapital() === 9000, 'Capital reduced by 1000');

// Update unrealized PnL
portfolio.updateUnrealizedPnL(110);
assert(portfolio.getUnrealizedPnL() === 100, 'Unrealized PnL is +100 (10 units * $10 gain)');

// Sell
const trades = portfolio.sell(110, 5);
assert(trades.length === 1, 'One sell trade created');
assert(trades[0].pnl === 50, 'Sell PnL is +50 (5 units * $10 gain)');
assert(portfolio.getCapital() === 9550, 'Capital after sell: 9000 + 550');

// Summary
const summary = portfolio.getSummary();
assert(summary.realizedPnL === 50, 'Realized PnL is 50');
assert(summary.tradeCount === 2, 'Trade count is 2 (1 buy + 1 sell)');

// Insufficient capital error
let buyError = false;
try { portfolio.buy(100, 1000); } catch { buyError = true; }
assert(buyError, 'Buy with insufficient capital throws');

// ─── ReputationManager ───
console.log('\n⭐ ReputationManager');
const rep = new ReputationManager();
assert(rep.getRep() === 0, 'Starting rep is 0');
assert(rep.getTier() === 1, 'Starting tier is 1');

rep.addRep(60, 'test_profit');
assert(rep.getRep() === 60, 'Rep is 60 after addRep(60)');
assert(rep.getTier() === 2, 'Tier upgraded to 2 at 60 rep');

// Leverage check
assert(rep.getMaxLeverage() === 5, 'Tier 2 max leverage is 5x');
assert(rep.canUnlockLeverage(3) === true, 'Can unlock 3x at tier 2');
assert(rep.canUnlockLeverage(8) === false, 'Cannot unlock 8x at tier 2');

// Tier change callback
let tierChangeNotified = false;
rep.onTierChange(() => { tierChangeNotified = true; });
rep.addRep(100, 'big_profit');
assert(tierChangeNotified, 'Tier change callback fired');
assert(rep.getTier() === 3, 'Tier is now 3');

// onTrade
rep.removeRep(200, 'reset_for_test');
rep.addRep(10, 'seed');
rep.onTrade(50);
assert(rep.getRep() > 10, 'onTrade(50) added reputation');

// ─── GasPenaltyManager ───
console.log('\n⛽ GasPenaltyManager');
const penalty = new GasPenaltyManager();
assert(penalty.getTotalOwed() === 0, 'No debt initially');

// Add debt
const debt = penalty.addDebt(1.0);
assert(debt.amount === 1.0, 'Debt amount is 1.0');
assert(penalty.getTotalOwed() === 1.0, 'Total owed is 1.0');

// Base fee enforcement
const smallDebt = penalty.addDebt(0.1);
assert(smallDebt.amount === 0.5, 'Debt below base fee gets clamped to $0.50');

// Mark paid
penalty.markPaid(debt.id);
assert(penalty.getActiveDebts().length === 1, 'One active debt remaining');

// Tick and doubling
for (let i = 0; i < 7; i++) penalty.tick();
const activeDebts = penalty.getActiveDebts();
assert(activeDebts.length === 1, 'Still 1 active debt');
assert(activeDebts[0].daysUnpaid === 7, 'Debt is 7 days unpaid');
assert(activeDebts[0].currentAmount === 1.0, 'Debt doubled after 7 days (0.5 → 1.0)');

// Credit multiplier
const expectedMult = Math.round((1.0 - (7 / 30) * 0.5) * 100) / 100;
assert(Math.abs(penalty.getCreditMultiplier() - expectedMult) < 0.01, `Credit multiplier is ~${expectedMult} at 7 days`);

// isBadTrade
assert(penalty.isBadTrade(-60, { entryPrice: 100, quantity: 10 }) === true, '60 loss on $1000 = bad trade');
assert(penalty.isBadTrade(-40, { entryPrice: 100, quantity: 10 }) === false, '40 loss on $1000 = ok');
assert(penalty.isBadTrade(10, { entryPrice: 100, quantity: 10 }) === false, 'Profit is never bad trade');

// ─── BotAdvisor ───
console.log('\n🤖 BotAdvisor');
const advisor = new BotAdvisor(market, portfolio, rep);
const analysis = advisor.analyze();
assert(['up', 'down', 'flat'].includes(analysis.trend), `Trend is valid: ${analysis.trend}`);
assert(['low', 'medium', 'high'].includes(analysis.volatility), `Volatility is valid: ${analysis.volatility}`);

const advice = advisor.getAdvice();
assert(['buy', 'sell', 'hold', 'reduce_leverage'].includes(advice.action), `Action is valid: ${advice.action}`);
assert(typeof advice.confidence === 'number' && advice.confidence >= 0 && advice.confidence <= 100, 'Confidence is 0-100');
assert(typeof advice.reason === 'string' && advice.reason.length > 0, 'Reason is non-empty string');
assert(typeof advice.message === 'string' && advice.message.length > 0, 'Message is non-empty string');
assert(typeof advice.id === 'string', 'Advice has an ID');

// Record outcome
const recorded = advisor.recordAdviceOutcome(advice.id, true);
assert(recorded === true, 'Advice outcome recorded');

// Stats
const stats = advisor.getStats();
assert(stats.totalAdvice === 1, 'Total advice is 1');
assert(stats.followed === 1, 'Followed count is 1');

// Double-record returns false
const doubleRecord = advisor.recordAdviceOutcome('fake_id', true);
assert(doubleRecord === false, 'Recording fake advice returns false');

// ─── Summary ───
console.log(`\n${'═'.repeat(40)}`);
console.log(`Results: ${passed} passed, ${failed} failed`);
console.log(`${'═'.repeat(40)}`);

process.exit(failed > 0 ? 1 : 0);
