/**
 * AQUORA - Responsive SVG Canal Depth Telemetry Chart
 * Renders multi-node water level time-series, datum lines, and wave threshold markers.
 * Clearly distinguishes physical ground-truth points from simulated points.
 */

class AquoraCanalChart {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.readingsByNode = {};
    this.activeFilter = "ALL";
    this.surgeThresholdCm = 15.0;
  }

  setReadings(nodeId, readings) {
    // Sort chronologically ascending
    const sorted = [...readings].sort((a, b) => new Date(a.timestamp_recorded) - new Date(b.timestamp_recorded));
    this.readingsByNode[nodeId] = sorted;
    this.render();
  }

  setFilter(filterNodeId) {
    this.activeFilter = filterNodeId;
    this.render();
  }

  render() {
    if (!this.container) return;

    // Aggregate points based on active filter
    let nodesToRender = Object.keys(this.readingsByNode);
    if (this.activeFilter !== "ALL") {
      nodesToRender = nodesToRender.filter(n => n === this.activeFilter);
    }

    let allPoints = [];
    nodesToRender.forEach(nodeId => {
      const list = this.readingsByNode[nodeId] || [];
      allPoints.push(...list);
    });

    if (allPoints.length === 0) {
      this.container.innerHTML = `
        <div class="chart-empty-state">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span>No telemetry readings available for selected reach.</span>
        </div>
      `;
      return;
    }

    // Chart dimensions
    const width = this.container.clientWidth || 800;
    const height = 240;
    const padding = { top: 25, right: 35, bottom: 35, left: 50 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    // Time domain & Level domain
    const times = allPoints.map(p => new Date(p.timestamp_recorded).getTime());
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times);
    const timeSpan = Math.max(1, maxTime - minTime);

    const levels = allPoints.map(p => p.water_level_cm);
    const maxLevel = Math.max(100.0, Math.ceil(Math.max(...levels) * 1.25));
    const minLevel = 0.0;

    const scaleX = (t) => padding.left + ((t - minTime) / timeSpan) * chartW;
    const scaleY = (lvl) => padding.top + chartH - ((lvl - minLevel) / (maxLevel - minLevel)) * chartH;

    // Color mapping by node
    const nodeColors = {
      "NODE-UPSTREAM-01": "#38bdf8",   // Cyan
      "NODE-MIDSTREAM-01": "#34d399",  // Emerald
      "NODE-DOWNSTREAM-02": "#c084fc", // Purple
    };

    // SVG assembly
    let svg = `<svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}" class="canal-svg-chart">`;

    // Gradients & Defs
    svg += `
      <defs>
        <linearGradient id="gradCyan" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
    `;

    // Grid lines & Y Axis labels
    const yTicks = [0, maxLevel * 0.25, maxLevel * 0.5, maxLevel * 0.75, maxLevel];
    yTicks.forEach(val => {
      const y = scaleY(val);
      svg += `
        <line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="4"/>
        <text x="${padding.left - 8}" y="${y + 4}" fill="#64748b" font-size="10" text-anchor="end" font-family="'JetBrains Mono', monospace">${val.toFixed(0)}cm</text>
      `;
    });

    // Surge Threshold Reference Line
    const surgeY = scaleY(this.surgeThresholdCm);
    svg += `
      <line x1="${padding.left}" y1="${surgeY}" x2="${width - padding.right}" y2="${surgeY}" stroke="rgba(251, 191, 36, 0.4)" stroke-dasharray="6,4" stroke-width="1.5"/>
      <text x="${width - padding.right}" y="${surgeY - 6}" fill="#fbbf24" font-size="9" text-anchor="end" font-weight="600">Surge Threshold (15cm)</text>
    `;

    // Render lines for each node
    nodesToRender.forEach(nodeId => {
      const points = this.readingsByNode[nodeId] || [];
      if (points.length < 1) return;

      const color = nodeColors[nodeId] || "#60a5fa";

      if (points.length === 1) {
        // Single point
        const pt = points[0];
        const cx = scaleX(new Date(pt.timestamp_recorded).getTime());
        const cy = scaleY(pt.water_level_cm);
        svg += `<circle cx="${cx}" cy="${cy}" r="5" fill="${color}"/>`;
        return;
      }

      // Build path line
      let pathD = "";
      points.forEach((p, idx) => {
        const x = scaleX(new Date(p.timestamp_recorded).getTime());
        const y = scaleY(p.water_level_cm);
        pathD += (idx === 0 ? "M" : "L") + `${x.toFixed(1)},${y.toFixed(1)}`;
      });

      svg += `<path d="${pathD}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`;

      // Render data points
      points.forEach((p) => {
        const cx = scaleX(new Date(p.timestamp_recorded).getTime());
        const cy = scaleY(p.water_level_cm);
        const isSim = p.is_simulated;
        const radius = isSim ? 4.5 : 4.0;
        const fill = isSim ? "#fbbf24" : color;
        const stroke = isSim ? "#0a0f1d" : "#ffffff";
        const titleText = `${nodeId}: ${p.water_level_cm.toFixed(1)} cm\nTime: ${new Date(p.timestamp_recorded).toLocaleTimeString()}\nType: ${isSim ? 'TEST SIMULATED' : 'PHYSICAL SENSOR'}`;

        svg += `
          <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${radius}" fill="${fill}" stroke="${stroke}" stroke-width="1.5" class="chart-point">
            <title>${titleText}</title>
          </circle>
        `;
      });
    });

    // Time Axis X Ticks
    const timeTicksCount = 4;
    for (let i = 0; i < timeTicksCount; i++) {
      const tVal = minTime + (timeSpan / (timeTicksCount - 1 || 1)) * i;
      const x = scaleX(tVal);
      const label = new Date(tVal).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      svg += `
        <text x="${x}" y="${height - 10}" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="'JetBrains Mono', monospace">${label}</text>
      `;
    }

    svg += `</svg>`;
    this.container.innerHTML = svg;
  }
}

window.AquoraCanalChart = AquoraCanalChart;
