/**
 * @module market
 * Simulated market engine with random walk, mean reversion, and volatility events.
 */

/**
 * @typedef {Object} MarketConfig
 * @property {number} initialPrice - Starting price (default 100)
 * @property {number} volatility - Per-tick volatility factor (default 0.02)
 * @property {number} tickInterval - Milliseconds between ticks (default 1000)
 * @property {number} meanReversion - Strength of pull toward initialPrice (default 0.001)
 * @property {number} [maxHistory] - Max price history entries (default 500)
 */

/**
 * Simulated market engine generating prices via random walk with mean reversion.
 * Supports volatility events (flash crashes, pumps) and subscriber notifications.
 */
export class MarketEngine {
  /** @type {number} */
  #price;
  /** @type {number} */
  #initialPrice;
  /** @type {number} */
  #volatility;
  /** @type {number} */
  #meanReversion;
  /** @type {number} */
  #maxHistory;
  /** @type {Array<{price: number, timestamp: number, event?: string}>} */
  #history;
  /** @type {Set<function>} */
  #subscribers;
  /** @type {ReturnType<typeof setInterval>|null} */
  #intervalId;
  /** @type {boolean} */
  #running;
  /** @type {number} */
  #tickCount;

  /**
   * Create a new MarketEngine.
   * @param {MarketConfig} [config]
   */
  constructor(config = {}) {
    const {
      initialPrice = 100,
      volatility = 0.02,
      tickInterval = 1000,
      meanReversion = 0.001,
      maxHistory = 500,
    } = config;

    this.#initialPrice = initialPrice;
    this.#price = initialPrice;
    this.#volatility = volatility;
    this.#meanReversion = meanReversion;
    this.#maxHistory = maxHistory;
    this.#history = [];
    this.#subscribers = new Set();
    this.#intervalId = null;
    this.#running = false;
    this.#tickCount = 0;

    // Store tickInterval for start()
    this._tickInterval = tickInterval;

    // Record initial price
    this.#history.push({ price: this.#price, timestamp: Date.now() });
  }

  /**
   * Start the market simulation.
   * Emits price updates at the configured tick interval.
   */
  start() {
    if (this.#running) return;
    this.#running = true;
    this.#intervalId = setInterval(() => this.#tick(), this._tickInterval);
  }

  /**
   * Stop the market simulation.
   */
  stop() {
    if (!this.#running) return;
    this.#running = false;
    if (this.#intervalId !== null) {
      clearInterval(this.#intervalId);
      this.#intervalId = null;
    }
  }

  /**
   * Subscribe to price updates.
   * @param {function} callback - Called with { price, timestamp, event? }
   * @returns {function} Unsubscribe function
   */
  subscribe(callback) {
    if (typeof callback !== 'function') {
      throw new TypeError('subscribe() requires a function callback');
    }
    this.#subscribers.add(callback);
    return () => this.#subscribers.delete(callback);
  }

  /**
   * Get the current market price.
   * @returns {number}
   */
  getCurrentPrice() {
    return this.#price;
  }

  /**
   * Get the full price history.
   * @returns {Array<{price: number, timestamp: number, event?: string}>}
   */
  getPriceHistory() {
    return [...this.#history];
  }

  /**
   * Get whether the market simulation is currently running.
   * @returns {boolean}
   */
  isRunning() {
    return this.#running;
  }

  /**
   * Get the total number of ticks elapsed.
   * @returns {number}
   */
  getTickCount() {
    return this.#tickCount;
  }

  /**
   * Manually advance one tick (useful for testing without interval).
   * @returns {{ price: number, timestamp: number, event?: string }}
   */
  manualTick() {
    return this.#tick();
  }

  /**
   * @private
   * Execute a single market tick: random walk + mean reversion + volatility events.
   * @returns {{ price: number, timestamp: number, event?: string }}
   */
  #tick() {
    this.#tickCount++;

    // Random walk component
    const randomWalk = (Math.random() * 2 - 1) * this.#volatility * this.#price;

    // Mean reversion component
    const reversion = this.#meanReversion * (this.#initialPrice - this.#price);

    let event = undefined;
    let adjustment = randomWalk + reversion;

    // 5% chance of a volatility event each tick
    if (Math.random() < 0.05) {
      if (Math.random() < 0.5) {
        // Flash crash: -10%
        adjustment = -0.10 * this.#price;
        event = 'flash_crash';
      } else {
        // Pump: +8%
        adjustment = 0.08 * this.#price;
        event = 'pump';
      }
    }

    this.#price = Math.max(0.01, this.#price + adjustment);

    const entry = { price: this.#price, timestamp: Date.now(), event };
    this.#history.push(entry);

    // Trim history if needed
    if (this.#history.length > this.#maxHistory) {
      this.#history.splice(0, this.#history.length - this.#maxHistory);
    }

    // Notify subscribers
    for (const cb of this.#subscribers) {
      try {
        cb(entry);
      } catch (err) {
        console.error('[MarketEngine] Subscriber error:', err);
      }
    }

    return entry;
  }
}
