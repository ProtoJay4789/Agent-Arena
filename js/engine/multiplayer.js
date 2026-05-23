/**
 * @module multiplayer
 * Simulated AI opponents with distinct trading strategies.
 *
 * Each opponent has a unique strategy, and responds to market ticks independently.
 * Supports event-driven market event notifications.
 */

/**
 * @typedef {Object} Opponent
 * @property {string} name - Unique trader name
 * @property {string} strategy - Trading strategy type
 * @property {number} capital - Available cash
 * @property {Array<{entryPrice: number, quantity: number, entryTime: number}>} positions - Open positions
 * @property {number} reputation - Reputation score
 * @property {number} totalPnL - Cumulative realized + unrealized P&L
 * @property {number} score - Score (alias for totalPnL for leaderboard)
 * @property {number} tradeCount - Total number of trades executed
 * @property {number} winCount - Number of profitable trades
 */

/**
 * @typedef {Object} Activity
 * @property {string} name - Trader name
 * @property {string} action - Action taken (buy/sell/hold/event)
 * @property {number} price - Execution price
 * @property {number} quantity - Units traded
 * @property {number} timestamp - When the action occurred
 * @property {string} [reason] - Strategy-specific reason
 */

/**
 * Simulated multiplayer engine that generates AI opponents with different trading behaviors.
 * Each opponent has a unique strategy and responds to market ticks independently.
 */
export class MultiplayerEngine {
  /** @type {Object} */
  #marketEngine;
  /** @type {Object|null} */
  #portfolioEngine;
  /** @type {Opponent[]} */
  #opponents;
  /** @type {Activity[]} */
  #activityLog;
  /** @type {number} */
  #tickCount;
  /** @type {Array<function(Object)>} */
  #marketEventCallbacks;

  /** Available opponent names */
  static NAMES = [
    'AlphaTrader',
    'DiamondHands',
    'PaperProfit',
    'ShadowWolf',
    'BullRunner',
    'SafeHarbor',
    'MoonShot',
    'GhostRider',
  ];

  /** Strategy definitions with behavior parameters */
  static STRATEGIES = {
    aggressive: {
      tradeChance: 0.40,
      positionSizePct: 0.35,
      stopLossPct: 0.15,
      takeProfitPct: 0.20,
      description: 'High risk, frequent trades',
    },
    conservative: {
      tradeChance: 0.10,
      positionSizePct: 0.10,
      stopLossPct: 0.05,
      takeProfitPct: 0.10,
      description: 'Low risk, hold long',
    },
    momentum: {
      tradeChance: 0.25,
      positionSizePct: 0.20,
      stopLossPct: 0.08,
      takeProfitPct: 0.12,
      description: 'Buy winners, sell losers',
    },
    contrarian: {
      tradeChance: 0.20,
      positionSizePct: 0.25,
      stopLossPct: 0.10,
      takeProfitPct: 0.15,
      description: 'Buy dips, sell peaks',
    },
  };

  /**
   * Create a new MultiplayerEngine.
   * @param {{ numPlayers?: number, marketEngine: Object, portfolioEngine?: Object }} config
   */
  constructor(config = {}) {
    const { numPlayers = 8, marketEngine, portfolioEngine = null } = config;

    if (!marketEngine) throw new TypeError('marketEngine is required');

    this.#marketEngine = marketEngine;
    this.#portfolioEngine = portfolioEngine;
    this.#activityLog = [];
    this.#tickCount = 0;
    this.#marketEventCallbacks = [];

    // Create opponents with assigned strategies
    const strategyKeys = ['aggressive', 'aggressive', 'conservative', 'conservative',
                          'momentum', 'momentum', 'contrarian', 'contrarian'];
    const names = MultiplayerEngine.NAMES.slice(0, numPlayers);

    this.#opponents = names.map((name, i) => ({
      name,
      strategy: strategyKeys[i % strategyKeys.length],
      capital: 10000,
      positions: [],
      reputation: 0,
      totalPnL: 0,
      score: 0,
      tradeCount: 0,
      winCount: 0,
    }));
  }

  /**
   * Register a callback for market events.
   * @param {function(Object)} callback - Called with event details when market events fire
   */
  onMarketEvent(callback) {
    if (typeof callback !== 'function') {
      throw new TypeError('onMarketEvent requires a function callback');
    }
    this.#marketEventCallbacks.push(callback);
  }

  /**
   * Called each market tick. Opponents evaluate and execute trades based on their strategy.
   */
  tick() {
    this.#tickCount++;
    const currentPrice = this.#marketEngine.getCurrentPrice();
    const history = this.#marketEngine.getPriceHistory();

    for (const opponent of this.#opponents) {
      this.#opponentTick(opponent, currentPrice, history);
    }

    // Random chance of triggering a market event (5% per tick)
    if (Math.random() < 0.05) {
      const event = this.triggerMarketEvent();
      for (const cb of this.#marketEventCallbacks) {
        try {
          cb(event);
        } catch (err) {
          console.error('[MultiplayerEngine] Market event callback error:', err);
        }
      }
    }
  }

  /**
   * Get the leaderboard sorted by score (highest first).
   * Includes all opponents and optionally the human player.
   * @returns {Array<{ name: string, score: number, capital: number, positions: number, tradeCount: number, winRate: number, isPlayer?: boolean }>}
   */
  getLeaderboard() {
    const entries = this.#opponents.map(o => ({
      name: o.name,
      score: o.score,
      totalPnL: o.totalPnL,
      capital: o.capital,
      positions: o.positions.length,
      tradeCount: o.tradeCount,
      winRate: o.tradeCount > 0 ? o.winCount / o.tradeCount : 0,
      isPlayer: false,
    }));

    // Add the human player if portfolio engine is available
    if (this.#portfolioEngine && typeof this.#portfolioEngine.getSummary === 'function') {
      const playerSummary = this.#portfolioEngine.getSummary();
      const history = typeof this.#portfolioEngine.getTradeHistory === 'function'
        ? this.#portfolioEngine.getTradeHistory()
        : [];
      const wins = history.filter(t => t.pnl !== null && t.pnl > 0).length;
      entries.push({
        name: 'Player',
        score: playerSummary.totalPnL,
        totalPnL: playerSummary.totalPnL,
        capital: playerSummary.capital,
        positions: playerSummary.openPositions,
        tradeCount: playerSummary.tradeCount,
        winRate: playerSummary.tradeCount > 0 ? wins / playerSummary.tradeCount : 0,
        isPlayer: true,
      });
    }

    // Sort by score descending
    entries.sort((a, b) => b.score - a.score);
    return entries;
  }

  /**
   * Get the last N activity entries from all opponents.
   * @param {number} [limit=5] - Number of recent actions to return
   * @returns {Activity[]}
   */
  getOpponentActivity(limit = 5) {
    return this.#activityLog.slice(-limit);
  }

  /**
   * Trigger a random market event that moves the price by 5-15%.
   * @returns {{ direction: string, magnitude: number, description: string, type: string }}
   */
  triggerMarketEvent() {
    const currentPrice = this.#marketEngine.getCurrentPrice();
    const magnitude = 0.05 + Math.random() * 0.10; // 5-15%
    const isUp = Math.random() > 0.5;

    const eventTypes = isUp
      ? ['bull_run', 'whale_buy', 'positive_news', 'fomo_surge']
      : ['bear_dump', 'whale_sell', 'negative_news', 'panic_selloff'];

    const eventType = eventTypes[Math.floor(Math.random() * eventTypes.length)];
    const direction = isUp ? 'up' : 'down';
    const percentChange = isUp ? magnitude : -magnitude;

    this.#logActivity('Market', 'event', currentPrice, 0,
      `${isUp ? '📈' : '📉'} ${eventType}: price ${(percentChange * 100).toFixed(1)}%`);

    const event = {
      direction,
      magnitude: Math.abs(percentChange),
      description: `${eventType.replace(/_/g, ' ')}: ${isUp ? '+' : ''}${(percentChange * 100).toFixed(1)}%`,
      type: eventType,
    };

    return event;
  }

  /**
   * Get all opponents.
   * @returns {Opponent[]}
   */
  getOpponents() {
    return this.#opponents.map(o => ({ ...o, positions: [...o.positions] }));
  }

  /**
   * Handle a single opponent's tick logic.
   * @private
   * @param {Opponent} opponent
   * @param {number} currentPrice
   * @param {Array} history
   */
  #opponentTick(opponent, currentPrice, history) {
    const strat = MultiplayerEngine.STRATEGIES[opponent.strategy];

    // First, check existing positions for stop loss / take profit
    this.#checkPositions(opponent, currentPrice);

    // Then consider opening new positions
    if (Math.random() < strat.tradeChance && opponent.capital > 100) {
      this.#decideEntry(opponent, currentPrice, history, strat);
    }
  }

  /**
   * Check an opponent's open positions for exit conditions.
   * @private
   */
  #checkPositions(opponent, currentPrice) {
    const strat = MultiplayerEngine.STRATEGIES[opponent.strategy];

    for (let i = opponent.positions.length - 1; i >= 0; i--) {
      const pos = opponent.positions[i];
      const pnlPct = (currentPrice - pos.entryPrice) / pos.entryPrice;

      let shouldSell = false;
      let reason = '';

      // Stop loss
      if (pnlPct <= -strat.stopLossPct) {
        shouldSell = true;
        reason = 'stop_loss';
      }
      // Take profit
      else if (pnlPct >= strat.takeProfitPct) {
        shouldSell = true;
        reason = 'take_profit';
      }
      // Strategy-specific exit logic
      else if (opponent.strategy === 'momentum') {
        const history = this.#marketEngine.getPriceHistory();
        const recentPrices = history.slice(-3);
        if (recentPrices.length === 3 &&
            recentPrices[0].price > recentPrices[1].price &&
            recentPrices[1].price > recentPrices[2].price) {
          shouldSell = true;
          reason = 'momentum_reversal';
        }
      }
      else if (opponent.strategy === 'conservative') {
        if (pnlPct <= -strat.stopLossPct * 1.5) {
          shouldSell = true;
          reason = 'conservative_exit';
        }
      }

      if (shouldSell) {
        const pnl = (currentPrice - pos.entryPrice) * pos.quantity;
        opponent.capital += pos.quantity * currentPrice;
        opponent.totalPnL += pnl;
        opponent.score = opponent.totalPnL;
        opponent.tradeCount++;
        if (pnl > 0) opponent.winCount++;

        this.#logActivity(opponent.name, 'sell', currentPrice, pos.quantity, reason);
        opponent.positions.splice(i, 1);
      }
    }
  }

  /**
   * Decide whether to enter a new position.
   * @private
   */
  #decideEntry(opponent, currentPrice, history, strat) {
    let shouldBuy = false;
    let reason = '';

    switch (opponent.strategy) {
      case 'aggressive':
        shouldBuy = true;
        reason = 'aggressive_entry';
        break;

      case 'conservative':
        if (history.length > 5) {
          const avgPrice = history.slice(-10).reduce((s, h) => s + h.price, 0) / Math.min(10, history.length);
          if (currentPrice < avgPrice * 0.97) {
            shouldBuy = true;
            reason = 'conservative_value';
          }
        }
        break;

      case 'momentum': {
        const recentPrices = history.slice(-3);
        if (recentPrices.length === 3 &&
            recentPrices[0].price < recentPrices[1].price &&
            recentPrices[1].price < recentPrices[2].price) {
          shouldBuy = true;
          reason = 'momentum_trend';
        }
        break;
      }

      case 'contrarian': {
        if (history.length > 5) {
          const recentHigh = Math.max(...history.slice(-10).map(h => h.price));
          if (currentPrice < recentHigh * 0.90) {
            shouldBuy = true;
            reason = 'contrarian_dip';
          }
        }
        break;
      }
    }

    if (shouldBuy) {
      const investAmount = Math.min(opponent.capital * strat.positionSizePct, opponent.capital - 100);
      if (investAmount < 50) return;

      const quantity = Math.floor(investAmount / currentPrice);
      if (quantity < 1) return;

      const cost = quantity * currentPrice;
      opponent.capital -= cost;
      opponent.positions.push({
        entryPrice: currentPrice,
        quantity,
        entryTime: Date.now(),
      });

      this.#logActivity(opponent.name, 'buy', currentPrice, quantity, reason);
    }
  }

  /**
   * Log an opponent activity entry.
   * @private
   */
  #logActivity(name, action, price, quantity, reason) {
    this.#activityLog.push({
      name,
      action,
      price,
      quantity,
      timestamp: Date.now(),
      reason: reason || '',
    });

    // Keep log from growing unbounded
    if (this.#activityLog.length > 1000) {
      this.#activityLog = this.#activityLog.slice(-500);
    }
  }
}
