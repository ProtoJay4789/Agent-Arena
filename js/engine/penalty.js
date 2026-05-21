/**
 * @module penalty
 * Gas penalty system tracking debts, fees, and credit health.
 */

/**
 * @typedef {Object} Debt
 * @property {string} id - Unique debt identifier
 * @property {number} amount - Original debt amount
 * @property {number} currentAmount - Current amount (may have doubled)
 * @property {number} daysUnpaid - How many days this debt has been unpaid
 * @property {number} timestamp - When the debt was created
 * @property {boolean} paid - Whether the debt has been settled
 */

/**
 * Manages gas penalties, debt tracking, and credit health.
 * Fees are $0.50 base, double every 7 days unpaid, and credit multiplier shrinks at 30 days.
 */
export class GasPenaltyManager {
  /** @type {Debt[]} */
  #debts;
  /** @type {number} */
  #totalOwed;
  /** @type {number} */
  #unpaidDays;
  /** @type {number} */
  #nextId;

  /** Base fee for a gas penalty */
  static BASE_FEE = 0.50;
  /** Days after which debt doubles */
  static DOUBLING_THRESHOLD = 7;
  /** Days after which credit multiplier starts shrinking */
  static CREDIT_SHRINK_THRESHOLD = 30;

  /**
   * Create a new GasPenaltyManager.
   */
  constructor() {
    this.#debts = [];
    this.#totalOwed = 0;
    this.#unpaidDays = 0;
    this.#nextId = 1;
  }

  /**
   * Generate the next unique debt ID.
   * @private
   * @returns {string}
   */
  #genId() {
    return `debt_${this.#nextId++}`;
  }

  /**
   * Add a new debt entry.
   * @param {number} amount - Debt amount (will be clamped to minimum base fee)
   * @returns {Debt} The created debt entry
   */
  addDebt(amount) {
    if (typeof amount !== 'number' || amount <= 0) {
      throw new RangeError('amount must be a positive number');
    }

    // Enforce minimum base fee
    const finalAmount = Math.max(amount, GasPenaltyManager.BASE_FEE);

    const debt = {
      id: this.#genId(),
      amount: finalAmount,
      currentAmount: finalAmount,
      daysUnpaid: 0,
      timestamp: Date.now(),
      paid: false,
    };

    this.#debts.push(debt);
    this.#totalOwed += finalAmount;

    return debt;
  }

  /**
   * Mark a specific debt as paid.
   * @param {string} debtId - The ID of the debt to mark as paid
   * @returns {boolean} True if the debt was found and marked, false otherwise
   */
  markPaid(debtId) {
    const debt = this.#debts.find(d => d.id === debtId);
    if (!debt || debt.paid) return false;

    debt.paid = true;
    this.#totalOwed -= debt.currentAmount;
    this.#totalOwed = Math.max(0, this.#totalOwed);

    return true;
  }

  /**
   * Advance one day. Increments unpaidDays on each active debt,
   * applies doubling rules, and updates total owed.
   * Call this once per in-game day.
   */
  tick() {
    this.#unpaidDays++;

    for (const debt of this.#debts) {
      if (debt.paid) continue;

      debt.daysUnpaid++;

      // Double the debt every DOUBLING_THRESHOLD days
      if (
        debt.daysUnpaid > 0 &&
        debt.daysUnpaid % GasPenaltyManager.DOUBLING_THRESHOLD === 0
      ) {
        // Recalculate: double the original amount for each doubling period
        const doublingPeriods = Math.floor(
          debt.daysUnpaid / GasPenaltyManager.DOUBLING_THRESHOLD
        );
        const newAmount = debt.amount * Math.pow(2, doublingPeriods);

        // Update totalOwed for the difference
        this.#totalOwed += (newAmount - debt.currentAmount);
        debt.currentAmount = newAmount;
      }
    }
  }

  /**
   * Get all active (unpaid) debts.
   * @returns {Debt[]}
   */
  getActiveDebts() {
    return this.#debts.filter(d => !d.paid);
  }

  /**
   * Get total amount currently owed across all active debts.
   * @returns {number}
   */
  getTotalOwed() {
    return this.#totalOwed;
  }

  /**
   * Get the global unpaid days counter.
   * @returns {number}
   */
  getUnpaidDays() {
    return this.#unpaidDays;
  }

  /**
   * Get the credit multiplier based on total unpaid days.
   * Starts at 1.0, drops to 0.5 at CREDIT_SHRINK_THRESHOLD days.
   * @returns {number} Multiplier between 0.5 and 1.0
   */
  getCreditMultiplier() {
    if (this.#unpaidDays >= GasPenaltyManager.CREDIT_SHRINK_THRESHOLD) {
      return 0.5;
    }
    // Linear interpolation from 1.0 to 0.5
    return 1.0 - (this.#unpaidDays / GasPenaltyManager.CREDIT_SHRINK_THRESHOLD) * 0.5;
  }

  /**
   * Determine if a trade would trigger a gas penalty.
   * A bad trade is a loss exceeding 5% of the position's notional value.
   * @param {number} pnl - The profit/loss of the trade (negative for losses)
   * @param {{ entryPrice: number, quantity: number }} position - The position being closed
   * @returns {boolean} True if the trade triggers a penalty
   */
  isBadTrade(pnl, position) {
    if (typeof pnl !== 'number') {
      throw new TypeError('pnl must be a number');
    }
    if (!position || typeof position.entryPrice !== 'number' || typeof position.quantity !== 'number') {
      throw new TypeError('position must have entryPrice and quantity');
    }

    if (pnl >= 0) return false;

    const notionalValue = position.entryPrice * position.quantity;
    const lossThreshold = notionalValue * 0.05;

    return Math.abs(pnl) > lossThreshold;
  }

  /**
   * Get summary of the penalty system state.
   * @returns {{
   *   totalOwed: number,
   *   activeDebtCount: number,
   *   unpaidDays: number,
   *   creditMultiplier: number,
   *   totalDebtsCreated: number
   * }}
   */
  getSummary() {
    return {
      totalOwed: this.#totalOwed,
      activeDebtCount: this.getActiveDebts().length,
      unpaidDays: this.#unpaidDays,
      creditMultiplier: this.getCreditMultiplier(),
      totalDebtsCreated: this.#debts.length,
    };
  }
}
