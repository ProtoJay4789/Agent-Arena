/**
 * @module whale
 * WhaleManipulator bot: periodically makes large market-moving trades, then follows its own push.
 */

/**
 * @typedef {Object} WhaleDecision
 * @property {'buy'|'sell'|'hold'} action - The recommended action
 * @property {number} confidence - Confidence level 0-1
 * @property {string} reason - Human-readable reason for the decision
 * @property {boolean} [isManipulation] - Whether this is a manipulation trade
 */

/**
 * @typedef {Object} ManipulationEntry
 * @property {string} type - 'buy' or 'sell'
 * @property {number} size - Trade size in capital
 * @property {number} timestamp - When the manipulation occurred
 * @property {number} tick - Tick number when it occurred
 * @property {string} rationale - Why this manipulation was chosen
 */

/**
 * Whale manipulation bot that periodically executes large trades to shift the market,
 * then trades in the direction it pushed. Has a cooldown between manipulations.
 *
 * Between manipulations, it trades normally following basic trend analysis.
 */
export class WhaleBot {
  /** @type {string} */
  #name;
  /** @type {number} */
  #capital;
  /** @type {number} */
  #initialCapital;
  /** @type {number} */
  #riskTolerance;
  /** @type {number} */
  #manipulationSize;
  /** @type {number} */
  #manipulationCooldown;
  /** @type {Array<{action: string, size: number, price: number, timestamp: number}>} */
  #positions;
  /** @type {string|null} */
  #lastAction;
  /** @type {number} */
  #pnl;
  /** @type {number} */
  #tickCount;
  /** @type {number} */
  #ticksSinceLastManipulation;
  /** @type {boolean} */
  #pendingFollowUp;
  /** @type {'buy'|'sell'|null} */
  #followUpDirection;
  /** @type {ManipulationEntry[]} */
  #manipulationHistory;

  /**
   * @param {Object} [opts]
   * @param {string} [opts.name='WhaleBot'] - Bot display name
   * @param {number} [opts.capital=50000] - Starting capital (higher for whale)
   * @param {number} [opts.riskTolerance=0.9] - Risk tolerance 0-1
   * @param {number} [opts.manipulationSize=0.15] - Fraction of capital per manipulation (0.15 = 15%)
   * @param {number} [opts.manipulationCooldown=20] - Ticks between manipulations
   */
  constructor({
    name = 'WhaleBot',
    capital = 50000,
    riskTolerance = 0.9,
    manipulationSize = 0.15,
    manipulationCooldown = 20,
  } = {}) {
    this.#name = name;
    this.#capital = capital;
    this.#initialCapital = capital;
    this.#riskTolerance = riskTolerance;
    this.#manipulationSize = manipulationSize;
    this.#manipulationCooldown = manipulationCooldown;
    this.#positions = [];
    this.#lastAction = null;
    this.#pnl = 0;
    this.#tickCount = 0;
    this.#ticksSinceLastManipulation = manipulationCooldown; // Ready on first tick
    this.#pendingFollowUp = false;
    this.#followUpDirection = null;
    this.#manipulationHistory = [];
  }

  /**
   * Analyze price history and decide on an action.
   * Strategy:
   *   1. If cooldown is up → execute a large manipulation trade (15% of capital)
   *   2. If there's a pending follow-up → trade in the same direction as the manipulation
   *   3. Otherwise → basic trend following (simplified momentum)
   *
   * @param {number[]} priceHistory - Array of recent prices (oldest first)
   * @returns {WhaleDecision}
   */
  analyze(priceHistory) {
    this.#tickCount++;
    this.#ticksSinceLastManipulation++;

    if (!priceHistory || priceHistory.length < 2) {
      return { action: 'hold', confidence: 0.5, reason: 'Insufficient price data for whale analysis.' };
    }

    const currentPrice = priceHistory[priceHistory.length - 1];
    if (currentPrice <= 0) {
      return { action: 'hold', confidence: 0.5, reason: 'Invalid price data.' };
    }

    // Phase 1: Pending follow-up after manipulation
    if (this.#pendingFollowUp && this.#followUpDirection) {
      const direction = this.#followUpDirection;
      this.#pendingFollowUp = false;
      this.#followUpDirection = null;

      return {
        action: direction,
        confidence: 0.8,
        reason: `Whale follow-up: reinforcing ${direction} position after market manipulation.`,
        isManipulation: false,
      };
    }

    // Phase 2: Cooldown expired — time to manipulate
    if (this.#ticksSinceLastManipulation >= this.#manipulationCooldown) {
      const decision = this._decideManipulation(priceHistory);
      if (decision) {
        this.#ticksSinceLastManipulation = 0;
        this.#pendingFollowUp = true;
        this.#followUpDirection = decision.action;

        // Record in history
        const manipSize = Math.round(this.#capital * this.#manipulationSize * 100) / 100;
        this.#manipulationHistory.push({
          type: decision.action,
          size: manipSize,
          timestamp: Date.now(),
          tick: this.#tickCount,
          rationale: decision.reason,
        });

        return decision;
      }
    }

    // Phase 3: Normal trading between manipulations
    return this._normalTrade(priceHistory);
  }

  /**
   * @private
   * Decide the direction for a market manipulation.
   * @param {number[]} priceHistory
   * @returns {WhaleDecision|null}
   */
  _decideManipulation(priceHistory) {
    const window = priceHistory.slice(-10);
    if (window.length < 2) return null;

    const oldest = window[0];
    const newest = window[window.length - 1];

    if (oldest <= 0) return null;

    const recentTrend = ((newest - oldest) / oldest) * 100;
    const manipSize = Math.round(this.#capital * this.#manipulationSize * 100) / 100;

    // Whale strategy: push against the current trend to profit from reversal
    // OR push with the trend to amplify it
    // We'll alternate: even ticks push with trend, odd ticks push against
    const pushWithTrend = this.#tickCount % 2 === 0;

    if (pushWithTrend || recentTrend === 0) {
      // Amplify the trend
      const direction = recentTrend >= 0 ? 'buy' : 'sell';
      return {
        action: direction,
        confidence: 0.95,
        reason: `🐋 WHALE MANIPULATION: Pushing ${direction} (${manipSize} | ${this.#manipulationSize * 100}% of capital) to amplify ${recentTrend >= 0 ? 'bullish' : 'bearish'} trend.`,
        isManipulation: true,
      };
    } else {
      // Counter-trend manipulation — try to reverse
      const direction = recentTrend >= 0 ? 'sell' : 'buy';
      return {
        action: direction,
        confidence: 0.9,
        reason: `🐋 WHALE MANIPULATION: Counter-push ${direction} (${manipSize} | ${this.#manipulationSize * 100}% of capital) to reverse ${recentTrend >= 0 ? 'bullish' : 'bearish'} move.`,
        isManipulation: true,
      };
    }
  }

  /**
   * @private
   * Normal trend-following trade between manipulations.
   * @param {number[]} priceHistory
   * @returns {WhaleDecision}
   */
  _normalTrade(priceHistory) {
    const window = priceHistory.slice(-5);
    if (window.length < 2) {
      return { action: 'hold', confidence: 0.5, reason: 'Whale resting — insufficient data for normal trade.' };
    }

    const oldest = window[0];
    const newest = window[window.length - 1];

    if (oldest <= 0) {
      return { action: 'hold', confidence: 0.5, reason: 'Invalid price data during whale rest period.' };
    }

    const changePct = ((newest - oldest) / oldest) * 100;
    const confBase = Math.min(Math.abs(changePct) / 5, 1) * this.#riskTolerance * 0.6;

    if (changePct > 1.5) {
      return {
        action: 'buy',
        confidence: Math.round(confBase * 100) / 100,
        reason: `Whale resting: basic uptrend (+${changePct.toFixed(2)}%) — making normal trade.`,
      };
    }

    if (changePct < -1.5) {
      return {
        action: 'sell',
        confidence: Math.round(confBase * 100) / 100,
        reason: `Whale resting: basic downtrend (${changePct.toFixed(2)}%) — making normal trade.`,
      };
    }

    return {
      action: 'hold',
      confidence: 0.4,
      reason: `Whale resting between manipulations. Market quiet (${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%).`,
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
   * @param {WhaleDecision} decision - Decision from analyze()
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
    const { action, confidence, isManipulation } = decision;

    if (action === 'hold') {
      this.#lastAction = 'hold';
      return { action: 'hold', success: true, size: 0 };
    }

    let size;
    if (isManipulation) {
      // Manipulation trades are larger (15% of capital)
      size = Math.round(this.#capital * this.#manipulationSize * 100) / 100;
    } else {
      // Normal trades scale with confidence
      const baseSize = this.#capital * this.#riskTolerance * confidence * 0.3;
      size = Math.round(baseSize * 100) / 100;
    }

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
   * Get the manipulation history for analysis/display.
   * @returns {ManipulationEntry[]}
   */
  getManipulationHistory() {
    return [...this.#manipulationHistory];
  }

  /**
   * Get the current bot status.
   * @returns {{ name: string, capital: number, positions: number, lastAction: string|null, pnl: number, ticksUntilManipulation: number }}
   */
  getStatus() {
    return {
      name: this.#name,
      capital: Math.round(this.#capital * 100) / 100,
      positions: this.#positions.length,
      lastAction: this.#lastAction,
      pnl: Math.round(this.#pnl * 100) / 100,
      ticksUntilManipulation: Math.max(0, this.#manipulationCooldown - this.#ticksSinceLastManipulation),
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
