/**
 * @module rep
 * Reputation system with tiered access to leverage.
 */

/**
 * Tier thresholds and their max leverage limits.
 * @type {Array<{tier: number, threshold: number, maxLeverage: number}>}
 */
const TIERS = [
  { tier: 1, threshold: 0,   maxLeverage: 1 },
  { tier: 2, threshold: 50,  maxLeverage: 5 },
  { tier: 3, threshold: 150, maxLeverage: 10 },
  { tier: 4, threshold: 400, maxLeverage: 20 },
];

/**
 * @typedef {Object} RepEntry
 * @property {number} amount - Amount of rep changed (positive or negative)
 * @property {number} reason - Reason code or description
 * @property {number} timestamp - When the change occurred
 * @property {number} totalAfter - Rep total after this change
 */

/**
 * Manages player reputation, tier progression, and leverage access.
 */
export class ReputationManager {
  /** @type {number} */
  #rep;
  /** @type {number} */
  #tier;
  /** @type {RepEntry[]} */
  #history;
  /** @type {Array<function(number, number)>} */
  #tierCallbacks;

  /**
   * Create a new ReputationManager.
   */
  constructor() {
    this.#rep = 0;
    this.#tier = 1;
    this.#history = [];
    this.#tierCallbacks = [];
  }

  /**
   * Register a callback for tier changes.
   * Callback receives (newTier, oldTier).
   * @param {function(number, number)} callback
   */
  onTierChange(callback) {
    if (typeof callback !== 'function') {
      throw new TypeError('onTierChange requires a function callback');
    }
    this.#tierCallbacks.push(callback);
  }

  /**
   * Add reputation points. Checks for tier upgrade.
   * @param {number} amount - Positive amount of rep to add
   * @param {string} [reason='manual'] - Reason for the change
   */
  addRep(amount, reason = 'manual') {
    if (typeof amount !== 'number' || amount <= 0) {
      throw new RangeError('amount must be a positive number');
    }

    this.#rep += amount;
    this.#recordEntry(amount, reason);
    this.#checkTier();
  }

  /**
   * Remove reputation points. Checks for tier downgrade.
   * @param {number} amount - Positive amount of rep to remove
   * @param {string} [reason='manual'] - Reason for the change
   */
  removeRep(amount, reason = 'manual') {
    if (typeof amount !== 'number' || amount <= 0) {
      throw new RangeError('amount must be a positive number');
    }

    this.#rep = Math.max(0, this.#rep - amount);
    this.#recordEntry(-amount, reason);
    this.#checkTier();
  }

  /**
   * Process a trade result. Positive PnL earns rep, negative loses it.
   * @param {number} pnl - Trade profit/loss (can be negative)
   */
  onTrade(pnl) {
    if (typeof pnl !== 'number') {
      throw new TypeError('pnl must be a number');
    }

    if (pnl > 0) {
      // Earn rep scaled by magnitude (capped per trade)
      const earned = Math.min(Math.floor(pnl * 0.5), 50);
      this.addRep(earned, `trade_profit_${pnl.toFixed(2)}`);
    } else if (pnl < 0) {
      // Lose rep scaled by magnitude (capped per trade)
      const lost = Math.min(Math.floor(Math.abs(pnl) * 0.3), 30);
      this.removeRep(lost, `trade_loss_${Math.abs(pnl).toFixed(2)}`);
    }
  }

  /**
   * Get the current reputation tier.
   * @returns {number} Tier number (1-4)
   */
  getTier() {
    return this.#tier;
  }

  /**
   * Get the current reputation points.
   * @returns {number}
   */
  getRep() {
    return this.#rep;
  }

  /**
   * Get the max leverage the player can unlock at their current tier.
   * @returns {number}
   */
  getMaxLeverage() {
    return TIERS.find(t => t.tier === this.#tier)?.maxLeverage ?? 1;
  }

  /**
   * Check if the player can unlock a specific leverage level.
   * @param {number} requestedLeverage - Desired leverage multiplier
   * @returns {boolean}
   */
  canUnlockLeverage(requestedLeverage) {
    if (typeof requestedLeverage !== 'number' || requestedLeverage < 1) {
      throw new RangeError('requestedLeverage must be >= 1');
    }
    return requestedLeverage <= this.getMaxLeverage();
  }

  /**
   * Get the full reputation history.
   * @returns {RepEntry[]}
   */
  getHistory() {
    return [...this.#history];
  }

  /**
   * Get rep needed to reach the next tier.
   * @returns {number} Rep remaining (0 if already max tier)
   */
  getRepToNextTier() {
    const nextTier = TIERS.find(t => t.tier === this.#tier + 1);
    if (!nextTier) return 0;
    return Math.max(0, nextTier.threshold - this.#rep);
  }

  /**
   * @private
   * Record a reputation entry.
   */
  #recordEntry(amount, reason) {
    this.#history.push({
      amount,
      reason,
      timestamp: Date.now(),
      totalAfter: this.#rep,
    });
  }

  /**
   * @private
   * Check and apply tier changes based on current rep.
   */
  #checkTier() {
    const oldTier = this.#tier;
    let newTier = 1;

    // Determine highest tier the player qualifies for
    for (const tierDef of TIERS) {
      if (this.#rep >= tierDef.threshold) {
        newTier = tierDef.tier;
      }
    }

    if (newTier !== oldTier) {
      this.#tier = newTier;

      // Notify all registered callbacks
      for (const cb of this.#tierCallbacks) {
        try {
          cb(newTier, oldTier);
        } catch (err) {
          console.error('[ReputationManager] Tier callback error:', err);
        }
      }
    }
  }
}
