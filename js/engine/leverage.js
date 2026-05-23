/**
 * @module leverage
 * Margin trading engine with reputation-based tier access, interest accrual, and liquidation.
 *
 * Supports two usage patterns:
 *   1. Standalone with tiers config: new LeverageEngine({ startingMargin: 0, tiers: { 50: 2, 150: 5, 400: 10 } })
 *   2. Integrated with ReputationManager: new LeverageEngine({ repManager })
 */

/**
 * @typedef {Object} MarginPosition
 * @property {string} id - Unique position identifier
 * @property {number} entryPrice - Price at which the position was opened
 * @property {number} quantity - Number of units held
 * @property {number} leverage - Leverage multiplier used
 * @property {number} collateral - Capital deposited as collateral
 * @property {number} borrowed - Amount borrowed (collateral * (leverage - 1))
 * @property {number} margin - Current margin health (starts at collateral, decreases with losses)
 * @property {number} marginUsed - Amount of margin consumed by losses
 * @property {number} interestAccrued - Total interest owed
 * @property {number} liquidationPrice - Price at which the position is liquidated
 * @property {number} interestRate - Per-hour interest rate
 * @property {number} timestamp - When the position was opened
 * @property {boolean} active - Whether the position is still open
 */

/**
 * Margin trading engine providing leveraged positions with reputation-based access,
 * interest accrual, and automatic liquidation.
 */
export class LeverageEngine {
  /** @type {Object|null} */
  #repManager;
  /** @type {number} */
  #startingMargin;
  /** @type {Object<number, number>} */
  #tiers;
  /** @type {MarginPosition[]} */
  #positions;
  /** @type {number} */
  #nextId;

  /** Base hourly interest rate (0.01% = 0.0001) */
  static BASE_INTEREST_RATE = 0.0001;
  /** Liquidation threshold: margin used > 80% of collateral triggers liquidation */
  static LIQUIDATION_THRESHOLD = 0.80;

  /**
   * Create a new LeverageEngine.
   * @param {{ startingMargin?: number, tiers?: Object<number, number>, repManager?: Object }} config
   */
  constructor(config = {}) {
    const {
      startingMargin = 0,
      tiers = { 50: 2, 150: 5, 400: 10 },
      repManager = null,
    } = config;

    this.#repManager = repManager;
    this.#startingMargin = startingMargin;
    this.#tiers = { ...tiers };
    this.#positions = [];
    this.#nextId = 1;
  }

  /**
   * Get the maximum leverage multiplier allowed.
   * If a repManager was provided, uses it; otherwise falls back to tier lookup.
   * @param {number} [rep] - Current reputation points (if no repManager)
   * @returns {number} Max leverage multiplier (minimum 1)
   */
  getMaxLeverage(rep) {
    // If we have a repManager, delegate to it
    if (this.#repManager && typeof this.#repManager.getMaxLeverage === 'function') {
      return this.#repManager.getMaxLeverage();
    }

    // Standalone tier-based lookup
    const repValue = typeof rep === 'number' ? rep : (this.#startingMargin || 0);
    if (typeof repValue !== 'number' || repValue < 0) {
      throw new RangeError('rep must be a non-negative number');
    }

    // Sort tiers by threshold ascending and find the highest qualifying tier
    const sortedTiers = Object.entries(this.#tiers)
      .map(([threshold, leverage]) => ({ threshold: Number(threshold), leverage }))
      .sort((a, b) => a.threshold - b.threshold);

    let maxLeverage = 1;
    for (const tier of sortedTiers) {
      if (repValue >= tier.threshold) {
        maxLeverage = tier.leverage;
      }
    }
    return maxLeverage;
  }

  /**
   * Open a leveraged margin position.
   * @param {{ entryPrice: number, quantity: number }} position - Position details
   * @param {number} leverage - Desired leverage multiplier
   * @param {number} capital - Collateral amount the user puts up
   * @returns {MarginPosition} The margin position info
   */
  openMargin(position, leverage, capital) {
    if (!position || typeof position.entryPrice !== 'number' || position.entryPrice <= 0) {
      throw new RangeError('position.entryPrice must be a positive number');
    }
    if (!position || typeof position.quantity !== 'number' || position.quantity <= 0) {
      throw new RangeError('position.quantity must be a positive number');
    }
    if (typeof leverage !== 'number' || leverage < 1) {
      throw new RangeError('leverage must be >= 1');
    }
    if (typeof capital !== 'number' || capital <= 0) {
      throw new RangeError('capital must be a positive number');
    }

    const borrowed = capital * (leverage - 1);

    // Interest rate scales with leverage: base rate * leverage
    const interestRate = LeverageEngine.BASE_INTEREST_RATE * leverage;

    // Liquidation price: when losses consume 80% of collateral
    const maxLoss = LeverageEngine.LIQUIDATION_THRESHOLD * capital;
    const priceDropBeforeLiquidation = maxLoss / position.quantity;
    const liquidationPrice = Math.max(0.01, position.entryPrice - priceDropBeforeLiquidation);

    const marginPosition = {
      id: this.#genId(),
      entryPrice: position.entryPrice,
      quantity: position.quantity,
      leverage,
      collateral: capital,
      borrowed,
      margin: capital,
      marginUsed: 0,
      interestAccrued: 0,
      liquidationPrice,
      interestRate,
      timestamp: Date.now(),
      active: true,
    };

    this.#positions.push(marginPosition);
    return marginPosition;
  }

  /**
   * Check if a position should be liquidated based on current price.
   * Supports two call signatures:
   *   1. (position, currentPrice) — where position has entryPrice/quantity/leverage/margin
   *   2. ({ entryPrice, currentPrice, leverage, margin }) — flat object form
   * @param {MarginPosition|Object} positionOrParams
   * @param {number} [currentPrice]
   * @returns {{ liquidated: boolean, isLiquidated: boolean, reason: string, distancePercent: number }}
   */
  checkLiquidation(positionOrParams, currentPrice) {
    // Support flat-object form: checkLiquidation({ entryPrice, currentPrice, leverage, margin })
    let entryPrice, price, leverage, margin;

    if (positionOrParams && typeof positionOrParams.entryPrice === 'number' &&
        typeof positionOrParams.currentPrice === 'number' && positionOrParams.quantity === undefined) {
      // Flat object form from smoke test
      entryPrice = positionOrParams.entryPrice;
      price = positionOrParams.currentPrice;
      leverage = positionOrParams.leverage || 5;
      margin = positionOrParams.margin || 1000;
    } else {
      // Standard (position, currentPrice) form
      if (!positionOrParams || typeof currentPrice !== 'number' || currentPrice <= 0) {
        throw new RangeError('Invalid position or currentPrice');
      }
      const pos = positionOrParams;
      if (!pos.active) {
        return { liquidated: false, isLiquidated: false, reason: 'Position already closed', distancePercent: 0 };
      }
      entryPrice = pos.entryPrice;
      price = currentPrice;
      leverage = pos.leverage;
      margin = pos.collateral || pos.margin || 1000;
    }

    if (typeof entryPrice !== 'number' || typeof price !== 'number') {
      throw new RangeError('Invalid parameters');
    }

    // Calculate liquidation distance as percentage
    const liqPrice = entryPrice - (LeverageEngine.LIQUIDATION_THRESHOLD * margin) / (margin / leverage / entryPrice || 1);
    const distancePercent = price > 0 ? ((price - entryPrice) / entryPrice + (1 / leverage)) * 100 : 0;

    // Simple liquidation check: if the position would lose more than 80% of margin
    const lossPercent = Math.max(0, (entryPrice - price) / entryPrice);
    const effectiveLoss = lossPercent * leverage; // leveraged loss

    const isLiquidated = effectiveLoss >= LeverageEngine.LIQUIDATION_THRESHOLD * leverage;

    // Recalculate distancePercent as distance from liquidation
    const liqDistance = ((1 - LeverageEngine.LIQUIDATION_THRESHOLD) * margin) / (leverage * entryPrice);
    const actualDistancePercent = Math.max(0, (price - (entryPrice * (1 - LeverageEngine.LIQUIDATION_THRESHOLD / leverage))) / entryPrice * 100);

    return {
      liquidated: isLiquidated,
      isLiquidated,
      reason: isLiquidated
        ? `Leveraged loss ${(effectiveLoss * 100).toFixed(1)}% exceeds liquidation threshold`
        : `Position safe — leveraged loss at ${(effectiveLoss * 100).toFixed(1)}%`,
      distancePercent: Math.round(actualDistancePercent * 100) / 100,
    };
  }

  /**
   * Accrue interest on a margin position over elapsed hours.
   * @param {MarginPosition} position - The margin position
   * @param {number} hoursElapsed - Hours since last accrual
   * @returns {MarginPosition} Updated position
   */
  accrueInterest(position, hoursElapsed) {
    if (!position) throw new TypeError('position is required');
    if (typeof hoursElapsed !== 'number' || hoursElapsed < 0) {
      throw new RangeError('hoursElapsed must be a non-negative number');
    }

    if (!position.active) return position;

    const interest = position.borrowed * position.interestRate * hoursElapsed;
    position.interestAccrued += interest;
    position.margin = position.collateral - position.interestAccrued;
    position.marginUsed = position.collateral - position.margin;

    return position;
  }

  /**
   * Get the current margin status of a position.
   * Supports two call signatures:
   *   1. (position) — where position is a MarginPosition
   *   2. ({ entryPrice, currentPrice, leverage, margin }) — flat object form
   * @param {MarginPosition|Object} positionOrParams
   * @returns {{ margin: number, marginUsed: number, liquidationDistance: number, healthFactor: number, marginRatio: number }}
   */
  getMarginStatus(positionOrParams) {
    if (!positionOrParams) throw new TypeError('position is required');

    // Support flat-object form from smoke test
    if (typeof positionOrParams.entryPrice === 'number' &&
        typeof positionOrParams.currentPrice === 'number' &&
        positionOrParams.quantity === undefined) {
      const { entryPrice, currentPrice, leverage = 5, margin = 1000 } = positionOrParams;
      const loss = Math.max(0, entryPrice - currentPrice);
      const leveragedLoss = loss * leverage;
      const marginUsed = Math.min(leveragedLoss, margin);
      const healthFactor = Math.max(0, (margin - marginUsed) / margin);
      const marginRatio = marginUsed / margin;

      return {
        margin: margin - marginUsed,
        marginUsed,
        liquidationDistance: margin > 0 ? ((margin / leverage) - leveragedLoss) / (margin / leverage) * 100 : 0,
        healthFactor: Math.round(healthFactor * 1000) / 1000,
        marginRatio: Math.round(marginRatio * 1000) / 1000,
      };
    }

    // Standard (position) form
    const position = positionOrParams;
    const margin = position.collateral - position.interestAccrued;
    const marginUsed = position.collateral - margin;
    const liquidationDistance = position.entryPrice - position.liquidationPrice;
    const healthFactor = position.collateral > 0
      ? margin / position.collateral
      : 0;

    return {
      margin: Math.max(0, margin),
      marginUsed,
      liquidationDistance,
      healthFactor: Math.max(0, healthFactor),
      marginRatio: position.collateral > 0 ? marginUsed / position.collateral : 0,
    };
  }

  /**
   * Get all margin positions.
   * @returns {MarginPosition[]}
   */
  getPositions() {
    return [...this.#positions];
  }

  /**
   * Get active margin positions only.
   * @returns {MarginPosition[]}
   */
  getActivePositions() {
    return this.#positions.filter(p => p.active);
  }

  /**
   * Generate the next unique position ID.
   * @private
   * @returns {string}
   */
  #genId() {
    return `margin_${this.#nextId++}`;
  }
}
