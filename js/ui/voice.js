/**
 * @module voice
 * Web Speech API integration for voice alerts and narration.
 */

/**
 * Voice engine providing text-to-speech for trade alerts,
 * liquidation warnings, leaderboard updates, and market events.
 * Falls back to console logging when Web Speech API is unavailable.
 */
export class VoiceEngine {
  /** @type {boolean} */
  #enabled;
  /** @type {number} */
  #rate;
  /** @type {number} */
  #pitch;
  /** @type {number} */
  #volume;
  /** @type {boolean} */
  #available;

  /**
   * @param {Object} [opts]
   * @param {boolean} [opts.enabled=true] - Whether voice is active
   * @param {number}  [opts.rate=1.0]     - Speech rate (0.1 – 10)
   * @param {number}  [opts.pitch=1.0]    - Speech pitch (0 – 2)
   * @param {number}  [opts.volume=0.8]   - Speech volume (0 – 1)
   */
  constructor(opts = {}) {
    this.#enabled = opts.enabled !== undefined ? opts.enabled : true;
    this.#rate = opts.rate || 1.0;
    this.#pitch = opts.pitch || 1.0;
    this.#volume = opts.volume !== undefined ? opts.volume : 0.8;
    this.#available = this.#checkAvailability();
  }

  /**
   * Check if the Web Speech API is available in this environment.
   * @returns {boolean}
   */
  #checkAvailability() {
    return (
      typeof window !== 'undefined' &&
      typeof window.speechSynthesis !== 'undefined' &&
      typeof window.SpeechSynthesisUtterance !== 'undefined'
    );
  }

  /**
   * Check if the Web Speech API is supported.
   * @returns {boolean}
   */
  isAvailable() {
    return this.#available;
  }

  /**
   * Speak text via Web Speech API, or log to console as fallback.
   * @param {string} text
   */
  speak(text) {
    if (!this.#enabled) return;

    if (this.#available) {
      const utterance = new window.SpeechSynthesisUtterance(text);
      utterance.rate = this.#rate;
      utterance.pitch = this.#pitch;
      utterance.volume = this.#volume;
      window.speechSynthesis.speak(utterance);
    } else {
      console.log(`[Voice] ${text}`);
    }
  }

  /**
   * Alert when a position is approaching liquidation.
   * @param {Object} position - { token: string, ... }
   */
  alertLiquidation(position) {
    const token = position.token || 'UNKNOWN';
    this.speak(`WARNING: Position in ${token} approaching liquidation!`);
  }

  /**
   * Alert when a trade is executed.
   * @param {Object} trade - { amount: number|string, token: string, price: number|string }
   */
  alertTrade(trade) {
    const amount = trade.amount || 0;
    const token = trade.token || 'UNKNOWN';
    const price = trade.price || 0;
    this.speak(`Trade executed: Bought ${amount} ${token} at $${price}`);
  }

  /**
   * Alert when the player's leaderboard rank changes.
   * @param {Object} position - position context
   * @param {number} rank - new rank
   */
  alertLeaderboard(position, rank) {
    this.speak(`You are now ranked #${rank} on the leaderboard`);
  }

  /**
   * Narrate a market event.
   * @param {Object} event - { type: string, description?: string, token?: string }
   */
  alertMarketEvent(event) {
    const type = event.type || 'unknown';
    const token = event.token || '';
    const desc = event.description || '';
    if (desc) {
      this.speak(`Market event: ${desc}`);
    } else if (token) {
      this.speak(`Market event: ${type} on ${token}`);
    } else {
      this.speak(`Market event: ${type}`);
    }
  }

  /**
   * Toggle voice on/off.
   * @returns {boolean} new enabled state
   */
  toggle() {
    this.#enabled = !this.#enabled;
    return this.#enabled;
  }

  /**
   * Get current enabled state.
   * @returns {boolean}
   */
  get enabled() {
    return this.#enabled;
  }
}
