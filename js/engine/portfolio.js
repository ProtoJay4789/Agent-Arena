/**
 * @module portfolio
 * Player portfolio management: positions, trades, and PnL tracking.
 */

/**
 * @typedef {Object} Position
 * @property {string} id - Unique position identifier
 * @property {number} entryPrice - Price at which the position was opened
 * @property {number} quantity - Number of units held
 * @property {number} entryTime - Timestamp when the position was opened
 * @property {number} unrealizedPnL - Current unrealized profit/loss
 */

/**
 * @typedef {Object} Trade
 * @property {string} id - Unique trade identifier
 * @property {'buy'|'sell'} type - Trade type
 * @property {number} price - Execution price
 * @property {number} quantity - Number of units traded
 * @property {number} timestamp - When the trade was executed
 * @property {number|null} pnl - Realized PnL (only for sells)
 */

/**
 * Manages a player's trading portfolio: capital, open positions, trade history, and PnL.
 */
export class Portfolio {
  /** @type {number} */
  #capital;
  /** @type {Position[]} */
  #positions;
  /** @type {Trade[]} */
  #tradeHistory;
  /** @type {number} */
  #realizedPnL;
  /** @type {number} */
  #unrealizedPnL;
  /** @type {number} */
  #nextId;

  /**
   * Create a new Portfolio.
   * @param {number} [startingCapital=10000] - Initial cash available for trading
   */
  constructor(startingCapital = 10000) {
    if (typeof startingCapital !== 'number' || startingCapital < 0) {
      throw new RangeError('startingCapital must be a non-negative number');
    }
    this.#capital = startingCapital;
    this.#positions = [];
    this.#tradeHistory = [];
    this.#realizedPnL = 0;
    this.#unrealizedPnL = 0;
    this.#nextId = 1;
  }

  /**
   * Generate the next unique ID.
   * @private
   * @returns {string}
   */
  #genId() {
    return `pos_${this.#nextId++}`;
  }

  /**
   * Execute a buy order: deduct capital and open a new position.
   * @param {number} price - Current market price
   * @param {number} quantity - Number of units to buy
   * @returns {Position} The newly created position
   * @throws {Error} If insufficient capital or invalid parameters
   */
  buy(price, quantity) {
    if (typeof price !== 'number' || price <= 0) {
      throw new RangeError('price must be a positive number');
    }
    if (typeof quantity !== 'number' || quantity <= 0) {
      throw new RangeError('quantity must be a positive number');
    }

    const cost = price * quantity;
    if (cost > this.#capital) {
      throw new Error(
        `Insufficient capital: need ${cost.toFixed(2)}, have ${this.#capital.toFixed(2)}`
      );
    }

    this.#capital -= cost;

    const position = {
      id: this.#genId(),
      entryPrice: price,
      quantity,
      entryTime: Date.now(),
      unrealizedPnL: 0,
    };
    this.#positions.push(position);

    /** @type {Trade} */
    const trade = {
      id: position.id,
      type: 'buy',
      price,
      quantity,
      timestamp: position.entryTime,
      pnl: null,
    };
    this.#tradeHistory.push(trade);

    return position;
  }

  /**
   * Execute a sell order: close positions using FIFO and realize PnL.
   * @param {number} price - Current market price
   * @param {number} quantity - Number of units to sell
   * @returns {Trade[]} Array of trades created (may be multiple if quantity spans positions)
   * @throws {Error} If insufficient open positions or invalid parameters
   */
  sell(price, quantity) {
    if (typeof price !== 'number' || price <= 0) {
      throw new RangeError('price must be a positive number');
    }
    if (typeof quantity !== 'number' || quantity <= 0) {
      throw new RangeError('quantity must be a positive number');
    }

    const totalOpen = this.#positions.reduce((sum, p) => sum + p.quantity, 0);
    if (quantity > totalOpen) {
      throw new Error(
        `Insufficient position: trying to sell ${quantity}, only ${totalOpen} open`
      );
    }

    const sellTrades = [];
    let remaining = quantity;

    // FIFO: close oldest positions first
    while (remaining > 0 && this.#positions.length > 0) {
      const pos = this.#positions[0];
      const sellQty = Math.min(remaining, pos.quantity);
      const pnl = (price - pos.entryPrice) * sellQty;

      // Create sell trade
      /** @type {Trade} */
      const trade = {
        id: this.#genId(),
        type: 'sell',
        price,
        quantity: sellQty,
        timestamp: Date.now(),
        pnl,
      };
      this.#tradeHistory.push(trade);
      sellTrades.push(trade);

      this.#realizedPnL += pnl;
      this.#capital += price * sellQty;

      pos.quantity -= sellQty;
      remaining -= sellQty;

      // Remove position if fully closed
      if (pos.quantity <= 0) {
        this.#positions.shift();
      }
    }

    return sellTrades;
  }

  /**
   * Recalculate unrealized PnL for all open positions based on current market price.
   * @param {number} currentPrice - Current market price
   * @returns {number} Total unrealized PnL across all positions
   */
  updateUnrealizedPnL(currentPrice) {
    if (typeof currentPrice !== 'number' || currentPrice <= 0) {
      throw new RangeError('currentPrice must be a positive number');
    }

    let total = 0;
    for (const pos of this.#positions) {
      pos.unrealizedPnL = (currentPrice - pos.entryPrice) * pos.quantity;
      total += pos.unrealizedPnL;
    }
    this.#unrealizedPnL = total;
    return total;
  }

  /**
   * Get all open positions.
   * @returns {Position[]}
   */
  getPositions() {
    return [...this.#positions];
  }

  /**
   * Get the full trade history.
   * @returns {Trade[]}
   */
  getTradeHistory() {
    return [...this.#tradeHistory];
  }

  /**
   * Get a summary of the portfolio state.
   * @returns {{
   *   capital: number,
   *   totalInvested: number,
   *   openPositions: number,
   *   realizedPnL: number,
   *   unrealizedPnL: number,
   *   totalPnL: number,
   *   tradeCount: number
   * }}
   */
  getSummary() {
    return {
      capital: this.#capital,
      totalInvested: this.#positions.reduce(
        (sum, p) => sum + p.entryPrice * p.quantity, 0
      ),
      openPositions: this.#positions.length,
      realizedPnL: this.#realizedPnL,
      unrealizedPnL: this.#unrealizedPnL,
      totalPnL: this.#realizedPnL + this.#unrealizedPnL,
      tradeCount: this.#tradeHistory.length,
    };
  }

  /**
   * Get current available capital.
   * @returns {number}
   */
  getCapital() {
    return this.#capital;
  }

  /**
   * Get total unrealized PnL.
   * @returns {number}
   */
  getUnrealizedPnL() {
    return this.#unrealizedPnL;
  }

  /**
   * Get realized PnL.
   * @returns {number}
   */
  getRealizedPnL() {
    return this.#realizedPnL;
  }
}
