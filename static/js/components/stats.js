import { escHtml, eventEmoji, timeAgo, timelineLink, durFromIso } from '/js/utils.js';
import { activeWorkers, statusEntries, projectScores } from '/js/state.js';

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
    card.innerHTML = `
      <div class="agent-header">
        <span class="agent-role">📦 <a class="project-name-link" href="#project/${encodeURIComponent(proj)}" data-project="${escHtml(proj)}">${escHtml(proj)}</a></span>
        <span class="status-badge ${status}">${status}</span>
      </div>
      <div class="agent-task">${isActive ? activeLines : lastLine || '<span style="color:var(--muted)">No activity yet</span>'}</div>
      <div class="agent-bounty">⭐ ${pts} pts</div>
    `;
    grid.appendChild(card);
  }
}
