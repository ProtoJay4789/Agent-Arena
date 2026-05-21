/**
 * AEG — Main App Controller
 * Orchestrates real engine modules and UI components
 */

import { MarketEngine } from '../engine/market.js';
import { Portfolio } from '../engine/portfolio.js';
import { ReputationManager } from '../engine/rep.js';
import { GasPenaltyManager } from '../engine/penalty.js';
import { BotAdvisor } from '../bots/advisor.js';
import { PriceChart } from './chart.js';
import { Dashboard } from './dashboard.js';

// ============================================
// App Controller
// ============================================
class App {
  constructor() {
    // Engine instances
    this.market = new MarketEngine({ initialPrice: 100, volatility: 0.02, tickInterval: 1000 });
    this.portfolio = new Portfolio(10000);
    this.reputation = new ReputationManager();
    this.penalty = new GasPenaltyManager();
    this.advisor = new BotAdvisor(this.market, this.portfolio, this.reputation);

    // UI instances
    this.chart = null;
    this.dashboard = null;

    // State
    this.tradeSide = 'buy';
    this.tickCounter = 0;
    this.TICKS_PER_DAY = 60;
    this.lastAdvisorTick = 0;

    // Unsubscribe handle
    this._unsubscribe = null;

    // Init
    this._init();
  }

  _init() {
    const firstVisit = !localStorage.getItem('aeg_visited');
    const savedState = localStorage.getItem('aeg_state');

    const overlay = document.getElementById('welcomeOverlay');
    const appEl = document.getElementById('app');
    const startBtn = document.getElementById('startBtn');

    if (firstVisit) {
      overlay.classList.remove('hidden');
      startBtn.addEventListener('click', () => {
        overlay.classList.add('hidden');
        appEl.classList.remove('hidden');
        localStorage.setItem('aeg_visited', '1');
        this._bootstrap();
      });
    } else {
      appEl.classList.remove('hidden');
      this._bootstrap();
    }

    // Load saved state (best-effort, private fields can't be set directly)
    // We store/load summary data only — positions need full engine restart
    if (savedState) {
      try {
        const data = JSON.parse(savedState);
        // Portfolio can't easily be hydrated with private fields,
        // so we note it and start fresh with saved capital hint
        if (data.portfolio && typeof data.portfolio.capital === 'number') {
          // We'll accept the default starting capital; state is lost on reload
          // This is a known limitation with private-field modules
        }
        if (data.reputation) {
          // Can't set private rep directly, but we log it
        }
        if (data.penalty) {
          // Same limitation
        }
      } catch (e) {
        console.warn('Failed to load saved state:', e);
      }
    }
  }

  _bootstrap() {
    // Init chart
    const canvas = document.getElementById('priceChart');
    this.chart = new PriceChart(canvas);

    // Init dashboard
    this.dashboard = new Dashboard();

    // Wire controls
    this._wireTradeControls();
    this._wireChat();
    this._wireDebt();
    this._wireCloseButtons();

    // Tier change notification
    this.reputation.onTierChange((newTier, oldTier) => {
      const tierNames = { 1: '1x Spot', 2: '2x-5x Leverage', 3: '10x Leverage', 4: '20x Leverage' };
      this.dashboard.addBotMessage(
        `🎉 TIER UP! You've reached Tier ${newTier}: ${tierNames[newTier] || 'Unknown'}. New leverage unlocked!`,
        'bot'
      );
    });

    // Initial bot welcome
    this.dashboard.addBotMessage(
      '🤖 Welcome to AEG! I\'m your Bot Advisor. I\'ll analyze the market and give you trading tips. Feel free to ask me anything!',
      'bot'
    );

    // Initial render
    this._refreshDashboard();

    // Subscribe to market ticks
    this._unsubscribe = this.market.subscribe((entry) => this._onTick(entry));

    // Start the market
    this.market.start();
  }

  _onTick(entry) {
    this.tickCounter++;
    const currentPrice = entry.price;
    const event = entry.event; // 'flash_crash' | 'pump' | undefined

    // Get price history as just prices for the chart
    const rawHistory = this.market.getPriceHistory();
    const prices = rawHistory.map(h => h.price);

    // Chart update with event marker
    let marker = null;
    if (event === 'flash_crash') {
      marker = { type: 'crash' };
    } else if (event === 'pump') {
      marker = { type: 'pump' };
    }
    this.chart.update(prices, marker);

    // Update price display
    const priceEl = document.getElementById('currentPrice');
    const changeEl = document.getElementById('priceChange');
    priceEl.textContent = '$' + currentPrice.toFixed(2);

    const firstPrice = prices[0] || currentPrice;
    const pctChange = ((currentPrice - firstPrice) / firstPrice) * 100;
    changeEl.textContent = (pctChange >= 0 ? '+' : '') + pctChange.toFixed(2) + '%';
    changeEl.className = 'chart-change ' + (pctChange > 0.01 ? 'positive' : pctChange < -0.01 ? 'negative' : 'neutral');

    // Update portfolio unrealized P&L
    this.portfolio.updateUnrealizedPnL(currentPrice);

    // Flash events → bot advisor warning
    if (event) {
      const type = event === 'flash_crash' ? 'crash' : 'pump';
      const msg = type === 'crash'
        ? '🚨 FLASH CRASH DETECTED! Price dropped 10% in one tick. This is exactly when panic selling destroys portfolios. Assess your positions rationally.'
        : '🚀 FLASH PUMP! Price surged 8% in one tick. These spikes are often followed by sharp reversals. Consider taking partial profits.';

      this.dashboard.addBotMessage(msg, 'warning');
      this.chart.addMarker(type);

      // Gas penalty on flash crash if holding positions
      if (type === 'crash' && this.portfolio.getPositions().length > 0) {
        this.penalty.addDebt(GasPenaltyManager.BASE_FEE);
      }
    }

    // Bot advisor analysis (throttled to every 5 ticks)
    if (this.tickCounter - this.lastAdvisorTick >= 5) {
      this.lastAdvisorTick = this.tickCounter;
      try {
        const advice = this.advisor.getAdvice();
        // Only show non-hold advice or every 5th hold
        if (advice.action !== 'hold' || this.tickCounter % 25 === 0) {
          this.dashboard.addBotMessage(advice.message, advice.action === 'sell' || advice.action === 'reduce_leverage' ? 'warning' : 'bot');
        }
      } catch (e) {
        // Silent fail for advisor errors
      }
    }

    // Day cycle
    if (this.tickCounter % this.TICKS_PER_DAY === 0) {
      this.penalty.tick();
      const totalOwed = this.penalty.getTotalOwed();
      if (totalOwed > 0) {
        this.reputation.removeRep(1, 'gas_debt_penalty');
        this.dashboard.addBotMessage(
          `⏰ Day cycle: You owe $${totalOwed.toFixed(2)} in gas fees. Pay it off to stop rep bleed (-1 rep/day).`,
          'system'
        );
      }
    }

    // Refresh dashboard
    this._refreshDashboard();

    // Auto-save
    if (this.tickCounter % 10 === 0) {
      this._saveState();
    }
  }

  _wireTradeControls() {
    const buyBtn = document.getElementById('buyBtn');
    const sellBtn = document.getElementById('sellBtn');
    const amountInput = document.getElementById('tradeAmount');
    const execBtn = document.getElementById('executeTrade');

    buyBtn.addEventListener('click', () => {
      this.tradeSide = 'buy';
      buyBtn.classList.add('active');
      sellBtn.classList.remove('active');
      execBtn.textContent = 'Execute Buy';
      execBtn.className = 'btn-primary btn-buy';
      this._updateQuantityPreview();
    });

    sellBtn.addEventListener('click', () => {
      this.tradeSide = 'sell';
      sellBtn.classList.add('active');
      buyBtn.classList.remove('active');
      execBtn.textContent = 'Execute Sell';
      execBtn.className = 'btn-primary btn-sell';
      this._updateQuantityPreview();
    });

    amountInput.addEventListener('input', () => this._updateQuantityPreview());
    execBtn.addEventListener('click', () => this._executeTrade());
  }

  _updateQuantityPreview() {
    const amount = parseFloat(document.getElementById('tradeAmount').value) || 0;
    const price = this.market.getCurrentPrice();
    const qty = amount / price;
    document.getElementById('quantityDisplay').textContent = qty.toFixed(4) + ' tokens';
  }

  _executeTrade() {
    const amount = parseFloat(document.getElementById('tradeAmount').value) || 0;
    if (amount <= 0) return;

    const price = this.market.getCurrentPrice();

    if (this.tradeSide === 'buy') {
      const quantity = amount / price;
      try {
        const position = this.portfolio.buy(price, quantity);
        this.reputation.addRep(2, 'trade_execution');
        this.dashboard.addBotMessage(
          `✅ Bought ${position.quantity.toFixed(4)} tokens at $${price.toFixed(2)}. Cost: $${amount.toFixed(2)}`,
          'bot'
        );
      } catch (e) {
        this.dashboard.addBotMessage(`⚠️ Buy failed: ${e.message}`, 'warning');
        return;
      }
    } else {
      // Sell: close the most recent position (or all if amount exceeds)
      const positions = this.portfolio.getPositions();
      if (positions.length === 0) {
        this.dashboard.addBotMessage('⚠️ No open positions to sell!', 'warning');
        return;
      }

      const amount = parseFloat(document.getElementById('tradeAmount').value) || 0;
      const sellQty = amount / price;

      try {
        const trades = this.portfolio.sell(price, sellQty);
        let totalPnl = 0;
        for (const trade of trades) {
          totalPnl += trade.pnl || 0;
          // Process rep through the reputation manager
          if (trade.pnl !== null) {
            this.reputation.onTrade(trade.pnl);
          }

          // Gas penalty for bad trades
          if (trade.pnl !== null && trade.pnl < 0) {
            // Find the position to check if it's a "bad trade"
            const notionalValue = trade.price * trade.quantity;
            if (Math.abs(trade.pnl) > notionalValue * 0.05) {
              this.penalty.addDebt(GasPenaltyManager.BASE_FEE);
              this.dashboard.addBotMessage('⛽ Gas fee added: $0.50 for this losing trade.', 'system');
            }
          }
        }

        const emoji = totalPnl >= 0 ? '🟢' : '🔴';
        this.dashboard.addBotMessage(
          `${emoji} Sold ${sellQty.toFixed(4)} tokens at $${price.toFixed(2)}. P&L: ${(totalPnl >= 0 ? '+' : '')}$${totalPnl.toFixed(2)}`,
          totalPnl >= 0 ? 'bot' : 'warning'
        );
      } catch (e) {
        this.dashboard.addBotMessage(`⚠️ Sell failed: ${e.message}`, 'warning');
        return;
      }
    }

    this._refreshDashboard();
    this._updateQuantityPreview();
  }

  _wireChat() {
    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('chatSend');

    setTimeout(() => {
      input.disabled = false;
      sendBtn.disabled = false;
    }, 2000);

    const send = () => {
      const text = input.value.trim();
      if (!text) return;
      this.dashboard.addBotMessage(text, 'player');

      // Use the real bot advisor for analysis
      setTimeout(() => {
        try {
          const analysis = this.advisor.analyze();
          const advice = this.advisor.getAdvice();

          // Generate a contextual response based on the question and analysis
          const q = text.toLowerCase();
          let response;

          if (q.includes('buy') || q.includes('long')) {
            if (analysis.trend === 'up') {
              response = `📈 Analysis says trend is UP with ${analysis.volatility} volatility. ${advice.action === 'buy' ? 'I agree — looks like a decent entry.' : 'But I\'d be cautious — my models suggest waiting.'}`;
            } else {
              response = `📊 Trend is ${analysis.trend} right now. Buying into a ${analysis.trend} market carries more risk. ${analysis.portfolioRisk === 'low' ? 'Your portfolio risk is low though, so a small position might work.' : 'Your portfolio risk is elevated — maybe hold off.'}`;
            }
          } else if (q.includes('sell') || q.includes('short') || q.includes('close')) {
            if (analysis.unrealizedLossPct > 10) {
              response = `⚠️ You have ${analysis.unrealizedLossPct.toFixed(1)}% unrealized losses. Cutting losses early is smart. A 10% loss locked in beats a 50% loss that evaporates.`;
            } else {
              response = `💡 Taking profits is always smart. ${analysis.trend === 'up' ? 'The trend is still up though — you might leave gains on the table.' : 'The trend is against you — selling could be wise.'}`;
            }
          } else if (q.includes('leverage')) {
            const maxLev = this.reputation.getMaxLeverage();
            response = `⚡ Your current tier allows up to ${maxLev}x leverage. ${analysis.overLeveraged ? 'Warning: you\'re already near your safe limit!' : 'You have room to grow, but start small.'} Build reputation through consistent profitable trades.`;
          } else if (q.includes('gas') || q.includes('debt')) {
            const totalOwed = this.penalty.getTotalOwed();
            const days = this.penalty.getUnpaidDays();
            response = `⛽ Current gas debt: $${totalOwed.toFixed(2)} (${days} days unpaid). ${totalOwed > 0 ? 'Pay it off to stop the -1 rep/day bleed. Debt doubles every 7 days!' : 'No debt — you\'re clean!'}`;
          } else if (q.includes('rep') || q.includes('tier') || q.includes('reputation')) {
            const rep = this.reputation.getRep();
            const tier = this.reputation.getTier();
            const toNext = this.reputation.getRepToNextTier();
            response = `🏆 Rep: ${rep} | Tier: ${tier} | ${toNext > 0 ? `${toNext} rep to next tier` : 'Max tier!'}. Profitable trades earn rep. Bad trades and gas debt cost rep.`;
          } else if (q.includes('help') || q.includes('how')) {
            response = `🎯 Quick guide: Trade USDC for tokens, watch the chart, listen to my advice. Profitable trades build rep → rep unlocks leverage tiers. Gas fees on bad trades create debt → unpaid debt bleeds rep. Manage risk wisely!`;
          } else {
            response = advice.message;
          }

          this.dashboard.addBotMessage(response, 'bot');
        } catch (e) {
          this.dashboard.addBotMessage('🤖 I\'m still analyzing the market. Ask me about buying, selling, leverage, gas fees, or reputation!', 'bot');
        }
      }, 400);

      input.value = '';
    };

    sendBtn.addEventListener('click', send);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') send();
    });
  }

  _wireDebt() {
    document.getElementById('payDebt').addEventListener('click', () => {
      const totalOwed = this.penalty.getTotalOwed();
      if (totalOwed <= 0) return;

      const capital = this.portfolio.getCapital();
      if (capital < totalOwed) {
        this.dashboard.addBotMessage(
          `⚠️ Not enough capital to pay debt. You need $${totalOwed.toFixed(2)} but only have $${capital.toFixed(2)}.`,
          'warning'
        );
        return;
      }

      // Pay off all active debts
      const activeDebts = this.penalty.getActiveDebts();
      for (const debt of activeDebts) {
        this.penalty.markPaid(debt.id);
      }

      this.dashboard.addBotMessage('✅ Gas debt cleared! No more reputation bleed.', 'bot');
      this._refreshDashboard();
    });
  }

  _wireCloseButtons() {
    document.getElementById('positionsBody').addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-close');
      if (!btn) return;

      const positionId = btn.dataset.position;
      const price = this.market.getCurrentPrice();

      // Find the position and sell all its quantity
      const positions = this.portfolio.getPositions();
      const pos = positions.find(p => p.id === positionId);
      if (!pos) return;

      try {
        const trades = this.portfolio.sell(price, pos.quantity);
        let totalPnl = 0;
        for (const trade of trades) {
          totalPnl += trade.pnl || 0;
          if (trade.pnl !== null) {
            this.reputation.onTrade(trade.pnl);
          }
          if (trade.pnl !== null && trade.pnl < 0) {
            const notionalValue = trade.price * trade.quantity;
            if (Math.abs(trade.pnl) > notionalValue * 0.05) {
              this.penalty.addDebt(GasPenaltyManager.BASE_FEE);
            }
          }
        }

        const emoji = totalPnl >= 0 ? '🟢' : '🔴';
        this.dashboard.addBotMessage(
          `${emoji} Position closed. P&L: ${(totalPnl >= 0 ? '+' : '')}$${totalPnl.toFixed(2)}`,
          totalPnl >= 0 ? 'bot' : 'warning'
        );
      } catch (e) {
        this.dashboard.addBotMessage(`⚠️ Close failed: ${e.message}`, 'warning');
      }

      this._refreshDashboard();
    });
  }

  _refreshDashboard() {
    const currentPrice = this.market.getCurrentPrice();
    const summary = this.portfolio.getSummary();

    // Portfolio
    this.dashboard.updatePortfolio({
      capital: summary.capital,
      totalPnl: summary.realizedPnL,
      unrealizedPnl: summary.unrealizedPnL,
    });

    // Positions with unrealized PnL
    const positions = this.portfolio.getPositions();
    this.dashboard.updatePositions(positions.map(p => ({
      ...p,
      unrealizedPnL: p.unrealizedPnL,
    })));

    // Rep
    this.dashboard.updateRep({
      score: this.reputation.getRep(),
      tier: this.reputation.getTier(),
    });

    // Debt
    this.dashboard.updateDebt({
      totalDebt: this.penalty.getTotalOwed(),
      unpaidDays: this.penalty.getUnpaidDays(),
    });

    // Trade history — convert to display format
    const trades = this.portfolio.getTradeHistory();
    const displayTrades = trades.map(t => ({
      side: t.type,
      price: t.price,
      quantity: t.quantity,
      pnl: t.pnl ?? 0,
    }));
    this.dashboard.updateTradeHistory(displayTrades);
  }

  _saveState() {
    try {
      const state = {
        portfolio: this.portfolio.getSummary(),
        reputation: { score: this.reputation.getRep(), tier: this.reputation.getTier() },
        penalty: this.penalty.getSummary(),
      };
      localStorage.setItem('aeg_state', JSON.stringify(state));
    } catch (e) {
      // Silent fail
    }
  }

  destroy() {
    if (this._unsubscribe) this._unsubscribe();
    this.market.stop();
  }
}

// ============================================
// Boot
// ============================================
document.addEventListener('DOMContentLoaded', () => {
  window.__aeg = new App();
});
