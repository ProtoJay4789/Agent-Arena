/**
 * AEG — Dashboard Renderer
 * Handles all DOM-based UI: portfolio, positions, rep, debt, trade history
 */

const TIER_INFO = {
  1: { label: '1x Spot', badge: 'T1', tierClass: 'tier-1' },
  2: { label: '2x-5x', badge: 'T2', tierClass: 'tier-2' },
  3: { label: '10x', badge: 'T3', tierClass: 'tier-3' },
  4: { label: '20x', badge: 'T4', tierClass: 'tier-4' },
};

const TIER_THRESHOLDS = {
  2: 100,
  3: 200,
  4: 350,
};

function fmt$(n) {
  const sign = n < 0 ? '-' : '';
  return sign + '$' + Math.abs(n).toFixed(2);
}

function fmtQty(n) {
  return n.toFixed(4);
}

function pnlClass(n) {
  if (n > 0.001) return 'positive';
  if (n < -0.001) return 'negative';
  return 'neutral';
}

function pnlPrefix(n) {
  if (n > 0.001) return '+ ';
  if (n < -0.001) return '';
  return '';
}

export class Dashboard {
  constructor() {
    // Cache DOM refs
    this.els = {
      capital: document.getElementById('capital'),
      totalPnl: document.getElementById('totalPnl'),
      unrealizedPnl: document.getElementById('unrealizedPnl'),
      positionsBody: document.getElementById('positionsBody'),
      repScore: document.getElementById('repScore'),
      tierBadge: document.getElementById('tierBadge'),
      tierLabel: document.getElementById('tierLabel'),
      repProgress: document.getElementById('repProgress'),
      repProgressLabel: document.getElementById('repProgressLabel'),
      debtTotal: document.getElementById('debtTotal'),
      debtDays: document.getElementById('debtDays'),
      payDebt: document.getElementById('payDebt'),
      tradeHistory: document.getElementById('tradeHistory'),
      headerCapital: document.getElementById('headerCapital'),
      headerPnl: document.getElementById('headerPnl'),
      chatArea: document.getElementById('chatArea'),
    };
  }

  updatePortfolio(portfolio) {
    if (!portfolio) return;
    const cap = portfolio.capital ?? portfolio.cash ?? 10000;
    const totalPnl = portfolio.totalPnl ?? portfolio.realizedPnl ?? 0;
    const unrealized = portfolio.unrealizedPnl ?? 0;

    this.els.capital.textContent = fmt$(cap);
    this.els.totalPnl.textContent = pnlPrefix(totalPnl) + fmt$(totalPnl);
    this.els.totalPnl.className = 'stat-value mono pnl ' + pnlClass(totalPnl);
    this.els.unrealizedPnl.textContent = pnlPrefix(unrealized) + fmt$(unrealized);
    this.els.unrealizedPnl.className = 'stat-value mono pnl ' + pnlClass(unrealized);

    // Header
    this.els.headerCapital.textContent = fmt$(cap);
    const netPnl = totalPnl + unrealized;
    this.els.headerPnl.textContent = pnlPrefix(netPnl) + fmt$(netPnl);
    this.els.headerPnl.className = 'header-stat pnl ' + pnlClass(netPnl);
  }

  updatePositions(positions) {
    const tbody = this.els.positionsBody;
    tbody.innerHTML = '';

    if (!positions || positions.length === 0) {
      tbody.innerHTML = '<tr class="empty-row"><td colspan="4">No open positions</td></tr>';
      return;
    }

    positions.forEach((pos) => {
      const tr = document.createElement('tr');
      const pnl = pos.unrealizedPnL ?? pos.unrealizedPnl ?? pos.pnl ?? 0;

      tr.innerHTML = `
        <td>${fmt$(pos.entryPrice)}</td>
        <td>${fmtQty(pos.quantity)}</td>
        <td class="pnl ${pnlClass(pnl)}">${pnlPrefix(pnl)}${fmt$(pnl)}</td>
        <td><button class="btn-close" data-position="${pos.id || ''}">Close</button></td>
      `;
      tbody.appendChild(tr);
    });
  }

  updateRep(repManager) {
    if (!repManager) return;
    const score = repManager.score ?? repManager.reputation ?? 50;
    const tier = repManager.tier ?? 1;

    const info = TIER_INFO[tier] || TIER_INFO[1];

    this.els.repScore.textContent = Math.round(score);
    this.els.tierBadge.textContent = info.badge;
    this.els.tierBadge.className = 'tier-badge ' + info.tierClass;
    this.els.tierLabel.textContent = info.label;

    // Progress to next tier
    const nextTier = tier + 1;
    let currentFloor = 0;
    let nextFloor = 100;
    if (TIER_THRESHOLDS[tier]) currentFloor = TIER_THRESHOLDS[tier];
    if (TIER_THRESHOLDS[nextTier]) nextFloor = TIER_THRESHOLDS[nextTier];

    if (tier >= 4) {
      this.els.repProgress.style.width = '100%';
      this.els.repProgressLabel.textContent = 'Max tier reached!';
    } else {
      const range = nextFloor - currentFloor;
      const progress = Math.min(100, Math.max(0, ((score - currentFloor) / range) * 100));
      this.els.repProgress.style.width = progress.toFixed(1) + '%';
      this.els.repProgressLabel.textContent = `${Math.round(score)} / ${nextFloor} to next tier`;
    }
  }

  updateDebt(penaltyManager) {
    if (!penaltyManager) return;
    const total = penaltyManager.totalDebt ?? penaltyManager.debt ?? 0;
    const days = penaltyManager.unpaidDays ?? 0;

    this.els.debtTotal.textContent = fmt$(total);
    this.els.debtDays.textContent = days;

    // Color coding
    this.els.debtTotal.className = 'stat-value mono';
    if (total <= 0) {
      this.els.debtTotal.classList.add('debt-safe');
    } else if (total < 1) {
      this.els.debtTotal.classList.add('debt-warn');
    } else {
      this.els.debtTotal.classList.add('debt-danger');
    }

    this.els.payDebt.disabled = total <= 0;
  }

  updateTradeHistory(trades) {
    const container = this.els.tradeHistory;
    container.innerHTML = '';

    if (!trades || trades.length === 0) {
      container.innerHTML = '<p class="empty-message">No trades yet</p>';
      return;
    }

    // Show most recent first, limit to 30
    const recent = trades.slice(-30).reverse();

    recent.forEach(t => {
      const div = document.createElement('div');
      div.className = 'history-item';
      const tradeSide = t.side || t.type || 'buy';
      const sideClass = tradeSide === 'buy' ? 'side-buy' : 'side-sell';
      const pnl = t.pnl ?? 0;
      const pnlStr = pnl !== 0 ? pnlPrefix(pnl) + fmt$(pnl) : '';
      const pnlCls = pnlClass(pnl);

      div.innerHTML = `
        <span class="${sideClass}">${tradeSide.toUpperCase()}</span>
        <span>${fmt$(t.price)} × ${fmtQty(t.quantity)}</span>
        <span class="hist-pnl ${pnlCls}">${pnlStr}</span>
      `;
      container.appendChild(div);
    });
  }

  addBotMessage(text, type = 'bot') {
    const area = this.els.chatArea;
    const msg = document.createElement('div');
    msg.className = 'chat-msg ' + type;

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    msg.innerHTML = `${text}<span class="timestamp">${time}</span>`;
    area.appendChild(msg);
    area.scrollTop = area.scrollHeight;
  }

  clearChat() {
    this.els.chatArea.innerHTML = '';
  }
}
