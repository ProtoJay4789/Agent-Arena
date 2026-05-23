/**
 * @module contrarian
 * ContrarianTrader bot: buys dips and sells peaks — goes against the crowd.
 */

/**
 * @typedef {Object} ContrarianDecision
 * @property {'buy'|'sell'|'hold'} action - The recommended action
 * @property {number} confidence - Confidence level 0-1
 * @property {string} reason - Human-readable reason for the decision
 */

/**
 * Contrarian trading bot that buys when the market dips and sells at peaks.
 * Tracks recent highs and lows to identify overextended moves.
 */
export class ContrarianBot {
  /** @type {string} */
  #name;
  /** @type {number} */
  #capital;
  /** @type {number} */
  #initialCapital;
  /** @type {number} */
  #riskTolerance;
  /** @type {number} */
  #dipThreshold;
  /** @type {number} */
  #peakThreshold;
  /** @type {Array<{action: string, size: number, price: number, timestamp: number}>} */
  #positions;
  /** @type {string|null} */
  #lastAction;
  /** @type {number} */
  #pnl;
  /** @type {number} */
  #tickCount;
  /** @type {number} */
  #recentHigh;
  /** @type {number} */
  #recentLow;
  /** @type {number} */
  #highWatermark;

  /**
   * @param {Object} [opts]
   * @param {string} [opts.name='ContrarianBot'] - Bot display name
   * @param {number} [opts.capital=10000] - Starting capital
   * @param {number} [opts.riskTolerance=0.5] - Risk tolerance 0-1
   * @param {number} [opts.dipThreshold=-5] - Percentage drop to trigger buy (-5 = 5% dip)
   * @param {number} [opts.peakThreshold=10] - Percentage rise from low to trigger sell (10 = 10% rise)
   */
  constructor({
    name = 'ContrarianBot',
    capital = 10000,
    riskTolerance = 0.5,
    dipThreshold = -5,
    peakThreshold = 10,
  } = {}) {
    this.#name = name;
    this.#capital = capital;
    this.#initialCapital = capital;
    this.#riskTolerance = riskTolerance;
    this.#dipThreshold = dipThreshold;
    this.#peakThreshold = peakThreshold;
    this.#positions = [];
    this.#lastAction = null;
    this.#pnl = 0;
    this.#tickCount = 0;
    this.#recentHigh = 0;
    this.#recentLow = Infinity;
    this.#highWatermark = 0;
  }

  /**
   * Analyze price history and decide on an action.
   * Strategy: Buy when price drops >dipThreshold% from recent high.
   *           Sell when price rises >peakThreshold% from recent low.
   *
   * @param {number[]} priceHistory - Array of recent prices (oldest first)
   * @returns {ContrarianDecision}
   */
  analyze(priceHistory) {
    this.#tickCount++;

    if (!priceHistory || priceHistory.length < 2) {
      return { action: 'hold', confidence: 0.5, reason: 'Insufficient price data.' };
    }

    const currentPrice = priceHistory[priceHistory.length - 1];
    if (currentPrice <= 0) {
      return { action: 'hold', confidence: 0.5, reason: 'Invalid price data.' };
    }

    // Track rolling high/low over a longer window (full history or last 50)
    const trackingWindow = priceHistory.slice(-50);
    const windowHigh = Math.max(...trackingWindow);
    const windowLow = Math.min(...trackingWindow);

    // Update tracked extremes
    if (windowHigh > this.#recentHigh || this.#tickCount <= 1) {
      this.#recentHigh = windowHigh;
    }
    if (windowLow < this.#recentLow || this.#tickCount <= 1) {
      this.#recentLow = windowLow;
    }

    // Update high watermark
    if (currentPrice > this.#highWatermark) {
      this.#highWatermark = currentPrice;
    }

    // Calculate drop from recent high (as percentage)
    const dropFromHigh = this.#recentHigh > 0
      ? ((currentPrice - this.#recentHigh) / this.#recentHigh) * 100
      : 0;

    // Calculate rise from recent low (as percentage)
    const riseFromLow = this.#recentLow > 0 && this.#recentLow < Infinity
      ? ((currentPrice - this.#recentLow) / this.#recentLow) * 100
      : 0;

    // BUY signal: price has dropped significantly from its high
    if (dropFromHigh <= this.#dipThreshold) {
      // Deeper dip = higher confidence
      const severity = Math.min(Math.abs(dropFromHigh) / Math.abs(this.#dipThreshold), 3);
      const confidence = Math.min((severity / 3) * this.#riskTolerance, 1);

      return {
        action: 'buy',
        confidence: Math.round(confidence * 100) / 100,
        reason: `Contrarian buy signal: price dropped ${Math.abs(dropFromHigh).toFixed(2)}% from recent high ($${this.#recentHigh.toFixed(2)}). Buying the dip.`,
      };
    }

    // SELL signal: price has risen significantly from its low
    if (riseFromLow >= this.#peakThreshold) {
      const severity = Math.min(riseFromLow / this.#peakThreshold, 3);
      const confidence = Math.min((severity / 3) * this.#riskTolerance, 1);

      return {
        action: 'sell',
        confidence: Math.round(confidence * 100) / 100,
        reason: `Contrarian sell signal: price rose ${riseFromLow.toFixed(2)}% from recent low ($${this.#recentLow.toFixed(2)}). Taking profits.`,
      };
    }

    // No signal — between thresholds
    const proximityBuy = Math.abs(dropFromHigh) / Math.abs(this.#dipThreshold);
    const proximitySell = riseFromLow / this.#peakThreshold;
    const proximity = Math.max(proximityBuy, proximitySell);

    return {
      action: 'hold',
      confidence: Math.round(Math.min(proximity, 1) * 50) / 100,
      reason: `No contrarian signal: ${dropFromHigh >= 0 ? '+' : ''}${dropFromHigh.toFixed(2)}% from high, +${riseFromLow.toFixed(2)}% from low. Watching for extremes.`,
    };
  }

  /**
   * Execute the decision by calling the provided trade function.
   * @param {function} tradeFn - Callback: (action, size, botName) => success
   * @returns {{ action: string, success: boolean, size: number }}
   */
  execute(tradeFn) {
    const decision = { action: 'hold', confidence: 0.5, reason: 'No price data — use analyze() first.' };
    return this._executeDecision(decision, tradeFn);
  }

  /**
   * Execute a specific decision.
   * @param {ContrarianDecision} decision - Decision from analyze()
   * @param {function} tradeFn - Callback: (action, size, botName) => success
   * @returns {{ action: string, success: boolean, size: number }}
   */
  executeDecision(decision, tradeFn) {
    return this._executeDecision(decision, tradeFn);
  }

  /**
   * @private
   */
  _executeDecision(decision, tradeFn) {
    const { action, confidence } = decision;

    if (action === 'hold') {
      this.#lastAction = 'hold';
      return { action: 'hold', success: true, size: 0 };
    }

    const baseSize = this.#capital * this.#riskTolerance * confidence;
    const size = Math.round(baseSize * 100) / 100;

    if (size <= 0 || this.#capital <= 0) {
      this.#lastAction = 'hold';
      return { action: 'hold', success: false, size: 0 };
    }

    let success = false;
    try {
      const result = tradeFn(action, size, this.#name);
      success = result !== false && result !== null && result !== undefined;
    } catch {
      success = false;
    }

    if (success) {
      this.#lastAction = action;
      this.#positions.push({
        action,
        size,
        price: 0,
        timestamp: Date.now(),
      });
    }

    return { action, success, size };
  }

  /**
   * Record the result of a trade.
   * @param {number} pnlChange - Profit/loss from the last trade
   */
  recordTradeResult(pnlChange) {
    this.#pnl += pnlChange;
    this.#capital += pnlChange;
  }

  /**
   * Update the tracked high/low externally (for when price arrives tick by tick).
   * @param {number} price - Current price
   */
  updatePrice(price) {
    if (price > this.#recentHigh) this.#recentHigh = price;
    if (price < this.#recentLow) this.#recentLow = price;
    if (price > this.#highWatermark) this.#highWatermark = price;
  }

  /**
   * Get the current bot status.
   * @returns {{ name: string, capital: number, positions: number, lastAction: string|null, pnl: number }}
   */
  getStatus() {
    return {
      name: this.#name,
      capital: Math.round(this.#capital * 100) / 100,
      positions: this.#positions.length,
      lastAction: this.#lastAction,
      pnl: Math.round(this.#pnl * 100) / 100,
    };
  }

  /**
   * Get the number of ticks this bot has been active.
   * @returns {number}
   */
  getTickCount() {
    return this.#tickCount;
  }
}
