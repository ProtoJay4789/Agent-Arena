/**
 * @module momentum
 * MomentumFollower bot: tracks price trends and trades in the direction of momentum.
 */

/**
 * @typedef {Object} MomentumDecision
 * @property {'buy'|'sell'|'hold'} action - The recommended action
 * @property {number} confidence - Confidence level 0-1
 * @property {string} reason - Human-readable reason for the decision
 */

/**
 * Momentum-following trading bot that buys during uptrends and sells during downtrends.
 * Tracks the last N prices and calculates percentage change over the lookback window.
 */
export class MomentumBot {
  /** @type {string} */
  #name;
  /** @type {number} */
  #capital;
  /** @type {number} */
  #initialCapital;
  /** @type {number} */
  #riskTolerance;
  /** @type {number} */
  #lookback;
  /** @type {Array<{action: string, size: number, price: number, timestamp: number}>} */
  #positions;
  /** @type {string|null} */
  #lastAction;
  /** @type {number} */
  #pnl;
  /** @type {number} */
  #tickCount;

  /**
   * @param {Object} [opts]
   * @param {string} [opts.name='MomentumBot'] - Bot display name
   * @param {number} [opts.capital=10000] - Starting capital
   * @param {number} [opts.riskTolerance=0.7] - Risk tolerance 0-1
   * @param {number} [opts.lookback=10] - Number of recent prices to analyze
   */
  constructor({ name = 'MomentumBot', capital = 10000, riskTolerance = 0.7, lookback = 10 } = {}) {
    this.#name = name;
    this.#capital = capital;
    this.#initialCapital = capital;
    this.#riskTolerance = riskTolerance;
    this.#lookback = lookback;
    this.#positions = [];
    this.#lastAction = null;
    this.#pnl = 0;
    this.#tickCount = 0;
  }

  /**
   * Analyze price history and decide on an action.
   * Strategy: If price trended up >2% over lookback window → BUY.
   *           If price trended down >2% → SELL.
   *           Otherwise → HOLD.
   *
   * @param {number[]} priceHistory - Array of recent prices (oldest first)
   * @returns {MomentumDecision}
   */
  analyze(priceHistory) {
    this.#tickCount++;

    if (!priceHistory || priceHistory.length < 2) {
      return { action: 'hold', confidence: 0.5, reason: 'Insufficient price data.' };
    }

    // Take last N prices for the lookback window
    const window = priceHistory.slice(-this.#lookback);
    const oldest = window[0];
    const newest = window[window.length - 1];

    if (oldest === 0) {
      return { action: 'hold', confidence: 0.5, reason: 'Price data contains zero values.' };
    }

    const changePct = ((newest - oldest) / oldest) * 100;

    // Calculate momentum strength (clamped 0-1)
    const rawConfidence = Math.min(Math.abs(changePct) / 10, 1);
    // Scale by risk tolerance
    const confidence = rawConfidence * this.#riskTolerance;

    if (changePct > 2) {
      // Strong uptrend — buy
      return {
        action: 'buy',
        confidence: Math.round(confidence * 100) / 100,
        reason: `Upward momentum detected: +${changePct.toFixed(2)}% over last ${window.length} ticks. Riding the trend.`,
      };
    }

    if (changePct < -2) {
      // Strong downtrend — sell
      return {
        action: 'sell',
        confidence: Math.round(confidence * 100) / 100,
        reason: `Downward momentum detected: ${changePct.toFixed(2)}% over last ${window.length} ticks. Cutting exposure.`,
      };
    }

    // No strong signal
    return {
      action: 'hold',
      confidence: Math.round((1 - rawConfidence) * 50) / 100,
      reason: `Weak momentum signal (${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%). Waiting for a clearer trend.`,
    };
  }

  /**
   * Execute the decision by calling the provided trade function.
   * @param {function} tradeFn - Callback: (action: string, size: number, botName: string) => boolean|number
   * @returns {{ action: string, success: boolean, size: number }}
   */
  execute(tradeFn) {
    // We need price history to make a decision, but execute doesn't receive it.
    // The caller should use analyze() first, then pass the result.
    // For standalone execution, we use a neutral hold.
    const decision = { action: 'hold', confidence: 0.5, reason: 'No price data in execute — use analyze() first.' };
    return this._executeDecision(decision, tradeFn);
  }

  /**
   * Execute a specific decision.
   * @param {MomentumDecision} decision - Decision from analyze()
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

    // Position sizing based on risk tolerance and confidence
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
        price: 0, // Price will be set by market engine
        timestamp: Date.now(),
      });
    }

    return { action, success, size };
  }

  /**
   * Record the result of a trade (called by market engine after execution).
   * @param {number} pnlChange - Profit/loss from the last trade
   */
  recordTradeResult(pnlChange) {
    this.#pnl += pnlChange;
    this.#capital += pnlChange;
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
