import { escHtml, eventEmoji, fmtDur, timeAgo, timelineLink, durFromIso } from '/js/utils.js';
import { activeWorkers, statusEntries, projectScores } from '/js/state.js';

function renderSparkline(runs) {
  const pts = (runs || []).filter(r => r.total_duration_seconds != null).slice(0, 7).reverse();
  if (pts.length < 2) return '';
  const vals = pts.map(r => r.total_duration_seconds);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const W = 60, H = 24, PAD = 2;
  const points = vals.map((v, i) => {
    const x = PAD + (i / (vals.length - 1)) * (W - PAD * 2);
    const y = PAD + (1 - (v - min) / range) * (H - PAD * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="display:block;margin-top:4px"><polyline points="${points}" fill="none" stroke="var(--accent2)" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

async function fetchAndRenderCycleTime(proj) {
  const panel = document.querySelector(`.agent-card[data-proj="${CSS.escape(proj)}"] .cycle-time-panel`);
  if (!panel) return;
  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(proj)}/cycle_times`);
    if (!res.ok) throw new Error('failed');
    const data = await res.json();
    const total = data.total_duration;
    if (!total || !total.sample_size) {
      panel.innerHTML = '<span style="color:var(--muted)">—</span>';
      return;
    }
    const median = fmtDur(total.median_seconds);
    const p90    = fmtDur(total.p90_seconds);
    const label  = `median: ${median} · P90: ${p90} · (last ${total.sample_size} runs)`;
    const runsRes  = await fetch(`/api/runs/${encodeURIComponent(proj)}`);
    const runsData = runsRes.ok ? await runsRes.json() : [];
    const spark    = renderSparkline(runsData);
    panel.innerHTML =
      `<span title="Median time from first event to completion, last ${total.sample_size} runs" style="color:var(--muted)">${escHtml(label)}</span>${spark}`;
  } catch {
    panel.innerHTML = '<span style="color:var(--muted)">—</span>';
  }
}

export function renderActive(workers) {
  const tbody = document.getElementById('active-workers-body');
  if (!workers.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="no-workers">No active workers — pipeline is idle</td></tr>';
    return;
  }
  tbody.innerHTML = workers.map(w => {
    const taskHtml = timelineLink(w.project, w.issue_number, w.pr_number);
    const since = w.created_at ? new Date(w.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';
    const dur = w.created_at ? durFromIso(w.created_at) : '—';
    const role = (w.role || '').charAt(0).toUpperCase() + (w.role || '').slice(1);
    const detail = w.detail ? `<div style="font-size:0.7rem;color:var(--muted);margin-top:2px">${escHtml(w.detail)}</div>` : '';
    return `
      <tr>
        <td><span class="worker-dot"></span></td>
        <td class="worker-project">${escHtml(w.project || '—')}</td>
        <td class="worker-role">${escHtml(role)}</td>
        <td class="worker-task">${taskHtml}${detail}</td>
        <td><span class="worker-event">${escHtml(w.event_type)}</span></td>
        <td class="worker-duration">${escHtml(since)}</td>
        <td class="worker-duration">${escHtml(dur)}</td>
      </tr>
    `;
  }).join('');
}

export function renderAgents() {
  const grid = document.getElementById('agent-grid');
  grid.innerHTML = '';

  const projects = new Map();
  for (const e of statusEntries) {
    if (!e.project) continue;
    if (!projects.has(e.project)) projects.set(e.project, { latest: e, active: [] });
    else if (e.id > projects.get(e.project).latest.id) projects.get(e.project).latest = e;
  }
  for (const w of activeWorkers) {
    if (!w.project) continue;
    if (!projects.has(w.project)) projects.set(w.project, { latest: w, active: [] });
    projects.get(w.project).active.push(w);
  }
  if (!projects.size) {
    grid.innerHTML = '<div style="color:var(--muted);font-size:0.8rem">No project data yet</div>';
    return;
  }
  for (const [proj, info] of [...projects.entries()].sort()) {
    const isActive = info.active.length > 0;
    const status = isActive ? 'busy' : 'idle';
    const pts = projectScores[proj] || 0;
    const activeLines = info.active.map(w =>
      `<div style="font-size:0.72rem;color:#818cf8;margin-top:2px">▶ ${escHtml(w.role)} ${escHtml(w.event_type)}${w.issue_number ? ' #' + w.issue_number : w.pr_number ? ' PR#' + w.pr_number : ''}</div>`
    ).join('');
    const lastEv = info.latest;
    const lastLine = !isActive && lastEv
      ? `<div style="font-size:0.72rem;color:var(--muted);margin-top:2px">${eventEmoji(lastEv.event_type)} ${escHtml(lastEv.event_type)} · ${escHtml(timeAgo(lastEv.created_at))}</div>`
      : '';
    const card = document.createElement('div');
    card.className = `agent-card ${status}`;
    card.dataset.proj = proj;
    card.innerHTML = `
      <div class="agent-header">
        <span class="agent-role">📦 <a class="project-name-link" href="#project/${encodeURIComponent(proj)}" data-project="${escHtml(proj)}">${escHtml(proj)}</a></span>
        <span class="status-badge ${status}">${status}</span>
      </div>
      <div class="agent-task">${isActive ? activeLines : lastLine || '<span style="color:var(--muted)">No activity yet</span>'}</div>
      <div class="agent-bounty">⭐ ${pts} pts</div>
      <div class="cycle-time-panel" style="margin-top:8px;font-size:0.7rem;color:var(--muted)">—</div>
    `;
    grid.appendChild(card);
  }

  for (const [proj] of [...projects.entries()].sort()) {
    fetchAndRenderCycleTime(proj);
  }
}
