/**
 * AEG — Price Chart Renderer
 * Pure canvas-based line chart with gradient fill, flash crash/pump markers
 */

export class PriceChart {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.data = [];
    this.maxPoints = 100;
    this.markers = []; // { index, type: 'crash'|'pump' }
    this.animFrame = null;
    this.dpr = window.devicePixelRatio || 1;
    this.padding = { top: 20, right: 60, bottom: 30, left: 10 };

    this._resize();
    window.addEventListener('resize', () => this._resize());
  }

  _resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height - (this.canvas.offsetTop || 0);
    this.canvas.width = w * this.dpr;
    this.canvas.height = h * this.dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.width = w;
    this.height = h;
    this.draw();
  }

  update(priceHistory, newMarker) {
    this.data = priceHistory.slice(-this.maxPoints);
    if (newMarker) {
      this.markers.push({ index: this.data.length - 1, type: newMarker.type });
      // Keep only recent markers
      if (this.markers.length > 20) this.markers.shift();
    }
    this.draw();
  }

  addMarker(type) {
    this.markers.push({ index: this.data.length - 1, type });
  }

  draw() {
    const { ctx, width: w, height: h, data, padding: p } = this;
    const drawW = w - p.left - p.right;
    const drawH = h - p.top - p.bottom;

    // Clear
    ctx.clearRect(0, 0, w, h);

    if (data.length < 2) {
      ctx.fillStyle = '#555';
      ctx.font = '13px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Waiting for price data...', w / 2, h / 2);
      return;
    }

    // Price range
    let min = Infinity, max = -Infinity;
    for (const d of data) {
      if (d < min) min = d;
      if (d > max) max = d;
    }
    const range = max - min || 1;
    const pad = range * 0.08;
    min -= pad;
    max += pad;

    const xStep = drawW / (data.length - 1);

    const toX = (i) => p.left + i * xStep;
    const toY = (v) => p.top + drawH - ((v - min) / (max - min)) * drawH;

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    const gridCount = 5;
    for (let i = 0; i <= gridCount; i++) {
      const y = p.top + (drawH / gridCount) * i;
      ctx.beginPath();
      ctx.moveTo(p.left, y);
      ctx.lineTo(w - p.right, y);
      ctx.stroke();
    }

    // Y-axis labels
    ctx.fillStyle = '#555';
    ctx.font = '10px monospace';
    ctx.textAlign = 'left';
    for (let i = 0; i <= gridCount; i++) {
      const val = max - (range + 2 * pad) * (i / gridCount);
      const y = p.top + (drawH / gridCount) * i;
      ctx.fillText('$' + val.toFixed(2), w - p.right + 5, y + 3);
    }

    // Determine line color based on trend
    const isUp = data[data.length - 1] >= data[0];
    const lineColor = isUp ? '#00ff88' : '#ff4444';

    // Area fill
    const gradient = ctx.createLinearGradient(0, p.top, 0, h - p.bottom);
    if (isUp) {
      gradient.addColorStop(0, 'rgba(0, 255, 136, 0.15)');
      gradient.addColorStop(1, 'rgba(0, 255, 136, 0.0)');
    } else {
      gradient.addColorStop(0, 'rgba(255, 68, 68, 0.15)');
      gradient.addColorStop(1, 'rgba(255, 68, 68, 0.0)');
    }

    ctx.beginPath();
    ctx.moveTo(toX(0), toY(data[0]));
    for (let i = 1; i < data.length; i++) {
      // Smooth curve
      const prevX = toX(i - 1);
      const prevY = toY(data[i - 1]);
      const curX = toX(i);
      const curY = toY(data[i]);
      const cpx = (prevX + curX) / 2;
      ctx.bezierCurveTo(cpx, prevY, cpx, curY, curX, curY);
    }
    ctx.lineTo(toX(data.length - 1), h - p.bottom);
    ctx.lineTo(toX(0), h - p.bottom);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.moveTo(toX(0), toY(data[0]));
    for (let i = 1; i < data.length; i++) {
      const prevX = toX(i - 1);
      const prevY = toY(data[i - 1]);
      const curX = toX(i);
      const curY = toY(data[i]);
      const cpx = (prevX + curX) / 2;
      ctx.bezierCurveTo(cpx, prevY, cpx, curY, curX, curY);
    }
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Glow effect on line
    ctx.shadowColor = lineColor;
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(toX(data.length - 1), toY(data[data.length - 1]));
    ctx.lineTo(toX(data.length - 1), toY(data[data.length - 1]));
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Current price dot
    const lastX = toX(data.length - 1);
    const lastY = toY(data[data.length - 1]);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = lineColor;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(lastX, lastY, 7, 0, Math.PI * 2);
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.3;
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Price label on right
    ctx.fillStyle = lineColor;
    ctx.font = 'bold 11px monospace';
    ctx.textAlign = 'right';
    ctx.fillText('$' + data[data.length - 1].toFixed(2), w - 5, lastY - 10);

    // Markers (flash crash / pump)
    for (const m of this.markers) {
      if (m.index < 0 || m.index >= data.length) continue;
      const mx = toX(m.index);
      const my = toY(data[m.index]);
      const color = m.type === 'crash' ? '#ff4444' : '#00ff88';

      ctx.beginPath();
      ctx.arc(mx, my, 5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.7;
      ctx.fill();
      ctx.globalAlpha = 1;

      // Marker label
      ctx.fillStyle = color;
      ctx.font = '9px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(m.type === 'crash' ? '⚠ CRASH' : '🚀 PUMP', mx, my - 10);
    }

    // X-axis time labels (simplified)
    ctx.fillStyle = '#444';
    ctx.font = '9px monospace';
    ctx.textAlign = 'center';
    const labelInterval = Math.max(1, Math.floor(data.length / 6));
    for (let i = 0; i < data.length; i += labelInterval) {
      const x = toX(i);
      ctx.fillText(`t-${data.length - i}`, x, h - p.bottom + 15);
    }
  }

  resize() {
    this._resize();
  }
}
