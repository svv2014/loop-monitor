import { escHtml, fmtDur } from '/js/utils.js';
import { setEventsGraphVisible } from '/js/state.js';

const STAGE_COLORS = {
  po:      '#6366f1',
  dev:     '#22d3ee',
  review:  '#fbbf24',
  qa:      '#34d399',
  merge:   '#4ade80',
  rework:  '#f59e0b',
  unknown: '#6b7590',
};
const STAGE_ORDER = ['po', 'dev', 'review', 'qa', 'merge', 'rework', 'unknown'];

const C_ACCENT  = '#6366f1';
const C_GREEN   = '#34d399';
const C_YELLOW  = '#fbbf24';
const C_RED     = '#f87171';
const PALETTE   = [C_ACCENT, C_GREEN, C_YELLOW, C_RED, '#22d3ee', '#a78bfa', '#fb923c', '#4ade80'];
const CHART_TICK = '#6b7590';
const CHART_GRID = '#2a2f3d';

let chartActivity = null;
let chartBoard    = null;
let chartStages   = null;

function chartScaleDefaults() {
  return {
    ticks: { color: CHART_TICK, font: { size: 10 } },
    grid:  { color: CHART_GRID },
  };
}

function lastNDays(n) {
  const days = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(d.toISOString().slice(0, 10));
  }
  return days;
}

export function renderEventsGraph(data) {
  const section = document.getElementById('events-graph-section');
  if (!data || !data.buckets) { section.style.display = 'none'; setEventsGraphVisible(false); return; }
  section.style.display = '';
  setEventsGraphVisible(true);

  const buckets = data.buckets || [];
  const windowHours = data.window_hours || 24;

  const now = new Date();
  now.setMinutes(0, 0, 0);
  const slots = [];
  for (let i = windowHours - 1; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 3600000);
    slots.push(d.toISOString().slice(0, 13));
  }

  const lookup = {};
  const rolesFound = new Set();
  for (const b of buckets) {
    const key = b.hour.slice(0, 13);
    if (!lookup[key]) lookup[key] = {};
    lookup[key][b.role] = (lookup[key][b.role] || 0) + b.count;
    rolesFound.add(b.role);
  }

  const roles = STAGE_ORDER.filter(r => rolesFound.has(r));
  for (const r of rolesFound) if (!STAGE_ORDER.includes(r)) roles.push(r);

  let maxCount = 1;
  for (const slot of slots) {
    const byRole = lookup[slot] || {};
    const total = Object.values(byRole).reduce((s, v) => s + v, 0);
    if (total > maxCount) maxCount = total;
  }

  const W = 1200, H = 140;
  const PL = 30, PR = 8, PT = 8, PB = 22;
  const bW = (W - PL - PR) / windowHours;
  const GAP = Math.max(1, bW * 0.12);
  const bAreaH = H - PT - PB;

  let svgContent = '';

  for (const frac of [0, 0.5, 1]) {
    const v = Math.round(frac * maxCount);
    const y = PT + bAreaH - frac * bAreaH;
    svgContent += `<line x1="${PL}" y1="${y.toFixed(1)}" x2="${W - PR}" y2="${y.toFixed(1)}" stroke="#2a2f3d" stroke-width="1"/>`;
    svgContent += `<text x="${PL - 4}" y="${(y + 3).toFixed(1)}" fill="#6b7590" font-size="9" text-anchor="end">${v}</text>`;
  }

  for (let i = 0; i < slots.length; i++) {
    const slot = slots[i];
    const byRole = lookup[slot] || {};
    const x = PL + i * bW + GAP / 2;
    const w = Math.max(1, bW - GAP);
    let yTop = PT + bAreaH;

    for (let ri = roles.length - 1; ri >= 0; ri--) {
      const role = roles[ri];
      const count = byRole[role] || 0;
      if (!count) continue;
      const rh = (count / maxCount) * bAreaH;
      yTop -= rh;
      const color = STAGE_COLORS[role] || STAGE_COLORS.unknown;
      const hLabel = slot.slice(11, 13) + ':00';
      svgContent += `<rect x="${x.toFixed(1)}" y="${yTop.toFixed(1)}" width="${w.toFixed(1)}" height="${rh.toFixed(1)}" fill="${color}" data-h="${hLabel}" data-r="${escHtml(role)}" data-c="${count}" style="cursor:default"/>`;
    }

    const hr = parseInt(slot.slice(11, 13), 10);
    if (hr % 6 === 0) {
      const lx = PL + (i + 0.5) * bW;
      svgContent += `<text x="${lx.toFixed(1)}" y="${H - 5}" fill="#6b7590" font-size="9" text-anchor="middle">${slot.slice(11, 13)}</text>`;
    }
  }

  document.getElementById('events-graph-svg').innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:${H}px;display:block">${svgContent}</svg>`;

  document.getElementById('events-graph-legend').innerHTML = roles.map(r => {
    const c = STAGE_COLORS[r] || STAGE_COLORS.unknown;
    return `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${c}"></span><span style="color:var(--muted);font-size:0.68rem">${r}</span></span>`;
  }).join('');
}

export function initCharts() {
  Chart.defaults.color = CHART_TICK;

  chartActivity = new Chart(document.getElementById('chart-activity'), {
    type: 'bar',
    data: { labels: [], datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: CHART_TICK, font: { size: 10 }, boxWidth: 12 } } },
      scales: {
        x: { ...chartScaleDefaults(), stacked: true },
        y: { ...chartScaleDefaults(), stacked: true },
      },
    },
  });

  chartBoard = new Chart(document.getElementById('chart-board'), {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Points', data: [], backgroundColor: C_ACCENT }] },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: chartScaleDefaults(),
        y: chartScaleDefaults(),
      },
    },
  });

  chartStages = new Chart(document.getElementById('chart-stages'), {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Avg min', data: [], backgroundColor: C_GREEN }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: chartScaleDefaults(),
        y: { ...chartScaleDefaults(), title: { display: true, text: 'minutes', color: CHART_TICK } },
      },
    },
  });
}

export function updateCharts(activityData, boardData, stagesData, reworkData) {
  const days = lastNDays(14);
  const projects = [...new Set(activityData.map(r => r.project))].sort();
  const actIdx = {};
  for (const r of activityData) actIdx[`${r.date}|${r.project}`] = r.n;

  chartActivity.data.labels   = days.map(d => d.slice(5));
  chartActivity.data.datasets = projects.map((proj, i) => ({
    label: proj,
    data:  days.map(d => actIdx[`${d}|${proj}`] || 0),
    backgroundColor: PALETTE[i % PALETTE.length],
  }));
  chartActivity.update('none');

  const projPts = {};
  for (const r of boardData) {
    const p = r.project || '';
    projPts[p] = (projPts[p] || 0) + r.total_points;
  }
  const projEntries = Object.entries(projPts).sort((a, b) => b[1] - a[1]);
  chartBoard.data.labels                     = projEntries.map(e => e[0]);
  chartBoard.data.datasets[0].data          = projEntries.map(e => e[1]);
  chartBoard.data.datasets[0].backgroundColor = projEntries.map((_, i) => PALETTE[i % PALETTE.length]);
  chartBoard.update('none');

  chartStages.data.labels            = stagesData.map(r => r.stage);
  chartStages.data.datasets[0].data = stagesData.map(r => +(r.avg_seconds / 60).toFixed(1));
  chartStages.update('none');

  const cards = document.getElementById('rework-cards');
  if (!reworkData.length) {
    cards.innerHTML = '<div class="empty-state">No data yet</div>';
    return;
  }
  cards.innerHTML = reworkData.map(r => {
    const rate = r.review_dones > 0
      ? (r.rework_starts / r.review_dones * 100).toFixed(1)
      : null;
    const colour = rate === null
      ? 'var(--muted)'
      : +rate > 30 ? C_RED : +rate > 10 ? C_YELLOW : C_GREEN;
    return `
      <div class="rework-card">
        <div class="rework-project">${escHtml(r.project)}</div>
        <div class="rework-rate" style="color:${colour}">${rate !== null ? rate + '%' : '—'}</div>
        <div class="rework-detail">${r.rework_starts} rework / ${r.review_dones} review</div>
      </div>`;
  }).join('');
}

export function initGraphTooltip() {
  const tip  = document.getElementById('graph-tooltip');
  const wrap = document.getElementById('events-graph-svg');
  wrap.addEventListener('mousemove', e => {
    const rect = e.target.closest('rect[data-h]');
    if (!rect) { tip.style.display = 'none'; return; }
    tip.textContent = `${rect.dataset.h} · ${rect.dataset.r}: ${rect.dataset.c}`;
    tip.style.display = 'block';
    tip.style.left = (e.clientX + 14) + 'px';
    tip.style.top  = (e.clientY - 30) + 'px';
  });
  wrap.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
}
