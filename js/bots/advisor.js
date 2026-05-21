/**
 * @module advisor
 * Bot advisor logic: analyzes market conditions and portfolio risk to provide trading advice.
 */

import { MarketEngine } from '../engine/market.js';
import { Portfolio } from '../engine/portfolio.js';
import { ReputationManager } from '../engine/rep.js';

/**
 * @typedef {Object} Advice
 * @property {string} id - Unique advice identifier
 * @property {'buy'|'sell'|'hold'|'reduce_leverage'} action - Recommended action
 * @property {number} confidence - Confidence level 0-100
 * @property {string} reason - Human-readable reason
 * @property {string} message - Personality-infused message for display
 * @property {number} timestamp - When the advice was generated
 */

/**
 * @typedef {Object} AdviceStats
 * @property {number} totalAdvice - Total pieces of advice given
 * @property {number} followed - Times player followed the advice
 * @property {number} ignored - Times player ignored the advice
 * @property {number} accuracy - Percentage of followed advice that was correct
 */

/**
 * Bot advisor that provides trading recommendations based on market conditions,
 * portfolio risk, and reputation tier.
 */
export class BotAdvisor {
  /** @type {MarketEngine} */
  #market;
  /** @type {Portfolio} */
  #portfolio;
  /** @type {ReputationManager} */
  #reputation;
  /** @type {Advice[]} */
  #adviceHistory;
  /** @type {Map<string, Advice>} */
  #pendingAdvice;
  /** @type {number} */
  #nextId;

  /**
   * Create a new BotAdvisor.
   * @param {MarketEngine} marketEngine - The market simulation instance
   * @param {Portfolio} portfolio - The player's portfolio
   * @param {ReputationManager} reputation - The reputation manager
   */
  constructor(marketEngine, portfolio, reputation) {
    if (!(marketEngine instanceof MarketEngine)) {
      throw new TypeError('marketEngine must be a MarketEngine instance');
    }
    if (!(portfolio instanceof Portfolio)) {
      throw new TypeError('portfolio must be a Portfolio instance');
    }
    if (!(reputation instanceof ReputationManager)) {
      throw new TypeError('reputation must be a ReputationManager instance');
    }

    this.#market = marketEngine;
    this.#portfolio = portfolio;
    this.#reputation = reputation;
    this.#adviceHistory = [];
    this.#pendingAdvice = new Map();
    this.#nextId = 1;
  }

  /**
   * Analyze current market and portfolio conditions.
   * @returns {{
   *   trend: 'up'|'down'|'flat',
   *   volatility: 'low'|'medium'|'high',
   *   portfolioRisk: 'low'|'medium'|'high'|'critical',
   *   overLeveraged: boolean,
   *   unrealizedLossPct: number
   * }}
   */
  analyze() {
    const history = this.#market.getPriceHistory();
    const currentPrice = this.#market.getCurrentPrice();
    const positions = this.#portfolio.getPositions();
    const summary = this.#portfolio.getSummary();

    // Determine trend from recent price history
    let trend = 'flat';
    if (history.length >= 10) {
      const recent = history.slice(-10);
      const first5Avg = recent.slice(0, 5).reduce((s, h) => s + h.price, 0) / 5;
      const last5Avg = recent.slice(-5).reduce((s, h) => s + h.price, 0) / 5;
      const changePct = (last5Avg - first5Avg) / first5Avg;

      if (changePct > 0.01) trend = 'up';
      else if (changePct < -0.01) trend = 'down';
    }

    // Estimate volatility from recent price swings
    let volatility = 'low';
    if (history.length >= 5) {
      const recent = history.slice(-5);
      let maxSwing = 0;
      for (let i = 1; i < recent.length; i++) {
        const swing = Math.abs(recent[i].price - recent[i - 1].price) / recent[i - 1].price;
        maxSwing = Math.max(maxSwing, swing);
      }
      if (maxSwing > 0.05) volatility = 'high';
      else if (maxSwing > 0.02) volatility = 'medium';
    }

    // Portfolio risk assessment
    let portfolioRisk = 'low';
    const unrealizedLossPct = summary.totalInvested > 0
      ? (Math.abs(Math.min(0, summary.unrealizedPnL)) / summary.totalInvested) * 100
      : 0;

    if (unrealizedLossPct > 20) portfolioRisk = 'critical';
    else if (unrealizedLossPct > 10) portfolioRisk = 'high';
    else if (unrealizedLossPct > 3) portfolioRisk = 'medium';

    // Check leverage status
    const maxLeverage = this.#reputation.getMaxLeverage();
    const invested = summary.totalInvested;
    const totalValue = summary.capital + invested;
    const currentLeverage = totalValue > 0 ? invested / totalValue : 0;
    const overLeveraged = currentLeverage > maxLeverage * 0.8;

    return {
      trend,
      volatility,
      portfolioRisk,
      overLeveraged,
      unrealizedLossPct,
    };
  }

  /**
   * Generate trading advice based on current analysis.
   * @returns {Advice} The advice object
   */
  getAdvice() {
    const analysis = this.analyze();
    let action = 'hold';
    let confidence = 50;
    let reason = '';

    // Priority 1: Over-leveraged — reduce exposure
    if (analysis.overLeveraged) {
      action = 'reduce_leverage';
      confidence = 85;
      reason = `Portfolio exposure exceeds safe leverage limits (risk: ${analysis.portfolioRisk}). Reduce positions.`;
    }
    // Priority 2: Large unrealized loss — suggest reducing
    else if (analysis.unrealizedLossPct > 10) {
      action = 'sell';
      confidence = 75;
      reason = `Unrealized losses at ${analysis.unrealizedLossPct.toFixed(1)}%. Consider cutting losses.`;
    }
    // Priority 3: Market trending up + small portfolio → suggest buying
    else if (analysis.trend === 'up' && analysis.portfolioRisk === 'low') {
      const summary = this.#portfolio.getSummary();
      if (summary.openPositions < 3) {
        action = 'buy';
        confidence = 65;
        reason = `Market trending upward with low portfolio risk. Opportunity to build position.`;
      }
    }
    // Priority 4: Market trending down → suggest caution
    else if (analysis.trend === 'down' && analysis.portfolioRisk !== 'low') {
      action = 'sell';
      confidence = 60;
      reason = `Market trending downward with existing exposure. Consider reducing.`;
    }
    // Priority 5: High volatility → hold and watch
    else if (analysis.volatility === 'high') {
      action = 'hold';
      confidence = 55;
      reason = `High market volatility detected. Wait for clearer signals.`;
    }
    // Default: hold
    else {
      action = 'hold';
      confidence = 50;
      reason = `Market conditions are neutral. No strong signal in either direction.`;
    }

    const id = this.#genId();
    const advice = {
      id,
      action,
      confidence,
      reason,
      message: '',
      timestamp: Date.now(),
    };

    // Generate the personality message
    advice.message = this.generateMessage(advice);

    // Store for tracking
    this.#adviceHistory.push(advice);
    this.#pendingAdvice.set(id, advice);

    return advice;
  }

  /**
   * Record whether the player followed the given advice.
   * @param {string} adviceId - The ID of the advice
   * @param {boolean} followed - Whether the player followed it
   * @returns {boolean} True if the advice was found
   */
  recordAdviceOutcome(adviceId, followed) {
    const advice = this.#pendingAdvice.get(adviceId);
    if (!advice) return false;

    // Store outcome on the advice object (not in typedef but functional)
    advice._followed = followed;
    this.#pendingAdvice.delete(adviceId);

    return true;
  }

  /**
   * Get statistics on advice accuracy.
   * @returns {AdviceStats}
   */
  getStats() {
    const totalAdvice = this.#adviceHistory.length;
    let followed = 0;
    let ignored = 0;

    for (const advice of this.#adviceHistory) {
      if (advice._followed === true) followed++;
      else if (advice._followed === false) ignored++;
    }

    const evaluated = followed + ignored;
    const accuracy = evaluated > 0 ? (followed / evaluated) * 100 : 0;

    return {
      totalAdvice,
      followed,
      ignored,
      accuracy: Math.round(accuracy * 10) / 10,
    };
  }

  /**
   * Generate a human-readable bot message with personality.
   * @param {Advice} advice - The advice object
   * @returns {string} A personality-infused message
   */
  generateMessage(advice) {
    const { action, confidence, reason } = advice;

    const greetings = [
      '🤖 Hey trader!',
      '📊 Market report incoming!',
      '💡 Quick insight:',
      '⚠️ Heads up, agent:',
      '🎯 Signal detected:',
    ];
    const greeting = greetings[Math.floor(Math.random() * greetings.length)];

    const actionPhrases = {
      buy: [
        'Time to stack some sats! I see an opportunity.',
        'The green candles are calling. Consider opening a position.',
        'Bullish vibes detected. Might be worth buying the dip.',
      ],
      sell: [
        'Protect those gains! I\'d consider taking some profit.',
        'The smart money might be heading for the exits. Think about selling.',
        'Risk is elevated. Consider trimming your position.',
      ],
      hold: [
        'Patience, young grasshopper. Hold your positions.',
        'No strong signal either way. Sit tight and observe.',
        'The market is indecisive. Let\'s wait for confirmation.',
      ],
      reduce_leverage: [
        'Whoa there, leverage cowboy! Dial it back before you get liquidated.',
        'Your risk levels are screaming. Reduce exposure immediately!',
        'Too much heat in the kitchen! Pull back on leverage.',
      ],
    };

    const phrases = actionPhrases[action] || actionPhrases.hold;
    const phrase = phrases[Math.floor(Math.random() * phrases.length)];

    return `${greeting}\n\n${phrase}\n\n📋 *Reason:* ${reason}\n💪 *Confidence:* ${confidence}%`;
  }

  /**
   * Get the full advice history.
   * @returns {Advice[]}
   */
  getAdviceHistory() {
    return [...this.#adviceHistory];
  }

  /**
   * @private
   * Generate the next unique advice ID.
   * @returns {string}
   */
  #genId() {
    return `adv_${this.#nextId++}`;
  }
}
