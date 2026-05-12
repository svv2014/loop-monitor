import { escHtml, fmtDur, ghLink, timelineLink } from '/js/utils.js';
import { eventsGraphVisible } from '/js/state.js';

const timelineCache = {};

const drawerEl      = document.getElementById('timeline-drawer');
const backdropEl    = document.getElementById('drawer-backdrop');
const projectPanel  = document.getElementById('project-panel');
const mainEl        = document.querySelector('main');
const chartsEl      = document.getElementById('charts-section');
const eventsGraphEl = document.getElementById('events-graph-section');

let currentProject = null;
let prMonitorInterval = null;

export function showProjectPanel(project) {
  document.getElementById('project-panel-title').textContent = project + ' — Run History';
  document.getElementById('runs-table-body').innerHTML =
    '<tr><td colspan="6" class="empty-state">Loading…</td></tr>';

  mainEl.style.display        = 'none';
  chartsEl.style.display      = 'none';
  eventsGraphEl.style.display = 'none';
  projectPanel.classList.add('active');

  history.pushState(null, '', '#project/' + encodeURIComponent(project));

  currentProject = project;
  fetch('/api/runs/' + encodeURIComponent(project))
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(payload => renderRunsTable(project, payload.runs || []))
    .catch(() => {
      document.getElementById('runs-table-body').innerHTML =
        '<tr><td colspan="6" style="color:var(--red);text-align:center;padding:16px">Failed to load runs</td></tr>';
    });

  loadPrMonitor(project);
  if (prMonitorInterval) clearInterval(prMonitorInterval);
  prMonitorInterval = setInterval(() => {
    if (currentProject) loadPrMonitor(currentProject);
  }, 60000);
}

export function showHome() {
  projectPanel.classList.remove('active');
  mainEl.style.display        = '';
  chartsEl.style.display      = '';
  eventsGraphEl.style.display = eventsGraphVisible ? '' : 'none';
  currentProject = null;
  if (prMonitorInterval) {
    clearInterval(prMonitorInterval);
    prMonitorInterval = null;
  }
}

let prMonitorRows = [];

function loadPrMonitor(project) {
  const includeFinished = document.getElementById('pr-include-finished')?.checked ? 'true' : 'false';
  fetch(`/api/projects/${encodeURIComponent(project)}/prs?include_finished=${includeFinished}`)
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(rows => {
      prMonitorRows = rows;
      populateStageFilter(rows);
      renderPrMonitor();
    })
    .catch(() => {
      const tbody = document.getElementById('pr-monitor-body');
      if (tbody) tbody.innerHTML =
        '<tr><td colspan="7" style="color:var(--red);text-align:center;padding:16px">Failed to load PRs</td></tr>';
    });
}

function populateStageFilter(rows) {
  const sel = document.getElementById('pr-stage-filter');
  if (!sel) return;
  const current = sel.value;
  const stages = Array.from(new Set(rows.map(r => r.stage).filter(Boolean))).sort();
  const opts = ['<option value="">All stages</option>']
    .concat(stages.map(s => `<option value="${escHtml(s)}">${escHtml(s)}</option>`));
  sel.innerHTML = opts.join('');
  if (stages.includes(current)) sel.value = current;
}

function timeBadgeClass(secs) {
  if (secs == null) return '';
  if (secs > 86400) return 'pr-time-red';
  if (secs > 21600) return 'pr-time-yellow';
  return 'pr-time-fresh';
}

function renderPrMonitor() {
  const tbody = document.getElementById('pr-monitor-body');
  if (!tbody) return;
  const stageFilter = document.getElementById('pr-stage-filter')?.value || '';
  const sortMode    = document.getElementById('pr-sort')?.value || 'age';

  let rows = prMonitorRows.slice();
  if (stageFilter) rows = rows.filter(r => r.stage === stageFilter);

  rows.sort((a, b) => {
    if (sortMode === 'stage') return (a.stage || '').localeCompare(b.stage || '');
    const av = a.time_in_stage_seconds ?? -1;
    const bv = b.time_in_stage_seconds ?? -1;
    return sortMode === 'age-desc' ? av - bv : bv - av;
  });

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No PRs tracked yet</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(r => {
    const cls   = timeBadgeClass(r.time_in_stage_seconds);
    const time  = r.time_in_stage_seconds != null ? fmtDur(r.time_in_stage_seconds) : '—';
    const stage = r.stage || '—';
    const draft = r.is_draft ? ' <span class="pr-draft-badge">draft</span>' : '';
    const branch = r.branch ? `<div style="color:var(--muted);font-size:0.7rem">${escHtml(r.branch)}</div>` : '';
    const finishedBadge = r.is_finished ? ' <span class="pr-finished-badge">done</span>' : '';
    const link  = r.github_url
      ? `<a href="${escHtml(r.github_url)}" target="_blank" rel="noopener" style="color:var(--muted);font-size:0.75rem">↗</a>`
      : '';
    return `<tr>
      <td>#${r.pr_number}${draft}${finishedBadge}</td>
      <td>${escHtml(r.title || '')}${branch}</td>
      <td><span class="stage-badge stage-${escHtml((stage).replace(/[^a-z0-9-]/gi,''))}">${escHtml(stage)}</span></td>
      <td class="${cls}">${escHtml(time)}</td>
      <td style="text-align:center">${r.retry_count || 0}</td>
      <td style="color:var(--muted);font-size:0.75rem">${escHtml(r.last_event || '—')}</td>
      <td>${link}</td>
    </tr>`;
  }).join('');
}

export function openDrawer(project, issue, pr) {
  const url = issue != null
    ? `/api/stats/timeline/${encodeURIComponent(project)}/${issue}`
    : `/api/stats/timeline/pr/${encodeURIComponent(project)}/${pr}`;

  document.getElementById('drawer-title').textContent    = issue != null ? `#${issue}` : `PR#${pr}`;
  document.getElementById('drawer-subtitle').textContent = project;
  document.getElementById('drawer-meta').innerHTML       = '<span style="color:var(--muted)">Loading…</span>';
  document.getElementById('drawer-stages').innerHTML     = '';
  document.getElementById('drawer-footer').innerHTML     = '';

  drawerEl.classList.add('open');
  backdropEl.classList.add('open');
  drawerEl.setAttribute('tabindex', '-1');
  drawerEl.focus();

  if (issue != null) {
    history.pushState(null, '', `#issue/${encodeURIComponent(project)}/${issue}`);
  }

  fetch(url)
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(data => populateDrawer(data, project, issue, pr))
    .catch(() => {
      document.getElementById('drawer-meta').innerHTML =
        '<span style="color:var(--red)">Failed to load timeline</span>';
    });
}

export function closeDrawer() {
  drawerEl.classList.remove('open');
  backdropEl.classList.remove('open');
  const h = window.location.hash;
  if (h && !h.startsWith('#project/')) {
    history.pushState(null, '', window.location.pathname + window.location.search);
  }
}

function populateDrawer(data, project, issue, pr) {
  const sum      = data.summary || {};
  const issueNum = data.issue_number != null ? data.issue_number : issue;
  const prNum    = sum.pr_number    != null ? sum.pr_number    : pr;
  const title    = sum.title || (issueNum != null ? `Issue #${issueNum}` : `PR #${prNum}`);

  document.getElementById('drawer-title').textContent    = title;
  document.getElementById('drawer-subtitle').textContent =
    `${project}${issueNum != null ? ' · #' + issueNum : ''}${prNum ? ' · PR#' + prNum : ''}`;

  const outcomeClass = sum.outcome === 'clean' ? 'pos' : sum.outcome ? 'neg' : 'zero';
  const outcomeLabel = sum.outcome || 'in progress';
  const durSecs      = sum.total_duration_seconds != null ? sum.total_duration_seconds : data.total_elapsed_seconds;
  const dur          = durSecs != null ? fmtDur(durSecs) : null;
  const reworkCount  = sum.rework_count || 0;

  let lifecycleBadge = '';
  if (sum.outcome && sum.issue_lifetime_seconds != null) {
    const mins = Math.round(sum.issue_lifetime_seconds / 60);
    const label = mins < 60 ? `${mins}m` : `${Math.floor(mins / 60)}h ${mins % 60}m`;
    const isMerged = sum.outcome === 'merged';
    const badgeClass = isMerged ? 'badge-merged' : 'badge-closed';
    const verb = isMerged ? 'merged' : 'closed';
    lifecycleBadge = `<span class="${badgeClass}">${verb} in ${label}</span>`;
  }

  document.getElementById('drawer-meta').innerHTML = [
    `<span class="verdict-pts ${outcomeClass}">${escHtml(outcomeLabel)}</span>`,
    lifecycleBadge,
    dur ? `<span class="drawer-meta-item">⏱ ${escHtml(dur)}</span>` : '',
    `<span class="drawer-meta-item">🔄 ${reworkCount} rework</span>`,
  ].filter(Boolean).join('');

  const stagesEl = document.getElementById('drawer-stages');
  const events   = data.events || [];
  if (!events.length) {
    stagesEl.innerHTML = '<div class="empty-state">No stage data yet</div>';
  } else {
    stagesEl.innerHTML = events.map(s => {
      const icon   = s.status === 'done' ? '✅' : s.status === 'failed' ? '❌' : '▶';
      const role   = (s.role || '').charAt(0).toUpperCase() + (s.role || '').slice(1);
      const time   = s.started_at
        ? new Date(s.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        : '';
      const durFmt = fmtDur(s.duration_seconds);
      const cumFmt = s.cumulative_seconds != null
        ? '+' + fmtDur(s.cumulative_seconds) + ' since opened'
        : '';
      return `
        <div class="stage-row">
          <span class="stage-icon">${icon}</span>
          <div class="stage-body">
            <span class="stage-role">${escHtml(role)}</span>
            <span class="stage-event">${escHtml(s.event_type)}</span>
            ${cumFmt ? `<div style="font-size:0.68rem;color:var(--muted)">${escHtml(cumFmt)}</div>` : ''}
          </div>
          <div class="stage-time">
            ${time   ? `<div>${escHtml(time)}</div>` : ''}
            ${durFmt ? `<div class="stage-dur">${escHtml(durFmt)}</div>` : ''}
          </div>
        </div>`;
    }).join('');
  }

  const repo   = data.repo;
  const footer = document.getElementById('drawer-footer');
  if (repo && issueNum != null) {
    footer.innerHTML = `<a class="drawer-gh-link" href="https://github.com/${escHtml(repo)}/issues/${issueNum}" target="_blank" rel="noopener">View on GitHub ↗</a>`;
  } else if (repo && prNum) {
    footer.innerHTML = `<a class="drawer-gh-link" href="https://github.com/${escHtml(repo)}/pull/${prNum}" target="_blank" rel="noopener">View on GitHub ↗</a>`;
  } else {
    footer.innerHTML = '';
  }
}

export function renderRunsTable(project, rows) {
  const tbody = document.getElementById('runs-table-body');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No runs yet for this project</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => {
    const issueCell = r.issue_number != null ? ghLink(project, r.issue_number, 'issue') : '—';
    const prCell    = r.pr_number    != null ? ghLink(project, r.pr_number,    'pull')  : '—';
    const dur       = r.total_duration_seconds != null ? fmtDur(r.total_duration_seconds) : '—';
    const rework    = r.rework_count != null ? r.rework_count : 0;
    const created   = r.created_at ? new Date(r.created_at).toLocaleDateString() : '—';
    const issueAttr = r.issue_number != null ? r.issue_number : '';
    const prAttr    = r.pr_number    != null ? r.pr_number    : '';
    const canExpand = r.issue_number != null;

    let outcomeHtml;
    if (r.outcome == null) {
      outcomeHtml = '<span class="outcome-badge null"><span class="pulse-badge"></span>in-flight</span>';
    } else if ((r.outcome || '').toLowerCase() === 'clean') {
      outcomeHtml = `<span class="outcome-badge clean">${escHtml(r.outcome)}</span>`;
    } else {
      outcomeHtml = `<span class="outcome-badge fail">${escHtml(r.outcome)}</span>`;
    }

    const toggleBtn = canExpand
      ? `<button class="expand-toggle" data-project="${escHtml(project)}" data-issue="${issueAttr}" aria-label="Expand stage breakdown">▶</button>`
      : '';

    return `<tr data-project="${escHtml(project)}" data-issue="${issueAttr}" data-pr="${prAttr}">
      <td style="width:32px">${toggleBtn}</td>
      <td>${issueCell}</td>
      <td>${prCell}</td>
      <td>${outcomeHtml}</td>
      <td style="color:var(--muted);font-size:0.78rem">${escHtml(dur)}</td>
      <td style="color:var(--muted);font-size:0.78rem">${rework}</td>
      <td style="color:var(--muted);font-size:0.75rem">${escHtml(created)}</td>
    </tr>`;
  }).join('');
}

function toggleExpandRow(project, issueNumber, btn) {
  const runRow = btn.closest('tr');
  const next   = runRow.nextElementSibling;
  const isOpen = btn.classList.contains('open');

  if (isOpen) {
    btn.classList.remove('open');
    btn.textContent = '▶';
    if (next && next.classList.contains('breakdown-row')) next.remove();
    return;
  }

  const cacheKey = `${project}|${issueNumber}`;
  if (timelineCache[cacheKey]) {
    insertBreakdownRow(runRow, timelineCache[cacheKey]);
    btn.classList.add('open');
    btn.textContent = '▼';
    return;
  }

  btn.textContent = '…';
  fetch(`/api/stats/timeline/${encodeURIComponent(project)}/${issueNumber}`)
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(data => {
      timelineCache[cacheKey] = data;
      insertBreakdownRow(runRow, data);
      btn.classList.add('open');
      btn.textContent = '▼';
    })
    .catch(() => {
      btn.textContent = '▶';
      btn.title = 'Failed to load timeline';
    });
}

function insertBreakdownRow(runRow, data) {
  const events       = data.events || [];
  const totalElapsed = data.total_elapsed_seconds != null
    ? data.total_elapsed_seconds
    : (data.summary && data.summary.total_duration_seconds != null
        ? data.summary.total_duration_seconds : null);

  let runningCum = 0;
  const rowsHtml = events.map(e => {
    const role   = (e.role || '').charAt(0).toUpperCase() + (e.role || '').slice(1);
    const status = e.status || '—';
    const dur    = e.duration_seconds != null ? fmtDur(e.duration_seconds) : '—';
    let cum;
    if (e.cumulative_seconds != null) {
      cum = fmtDur(e.cumulative_seconds);
    } else if (e.duration_seconds != null) {
      runningCum += e.duration_seconds;
      cum = fmtDur(runningCum);
    } else {
      cum = '—';
    }
    return `<tr>
      <td class="bd-role">${escHtml(role)}</td>
      <td>${escHtml(status)}</td>
      <td class="bd-dur">${escHtml(dur)}</td>
      <td class="bd-cum">${escHtml(cum)}</td>
    </tr>`;
  }).join('');

  const footerHtml = totalElapsed != null
    ? `<tr class="bd-foot"><td colspan="2">Total elapsed</td><td class="bd-dur" colspan="2">${escHtml(fmtDur(totalElapsed))}</td></tr>`
    : '';

  const breakdownRow = document.createElement('tr');
  breakdownRow.className = 'breakdown-row';
  breakdownRow.innerHTML = `<td colspan="7"><div class="breakdown-inner">${
    events.length
      ? `<table class="breakdown-table"><thead><tr><th>Role</th><th>Status</th><th>Duration</th><th>Cumulative</th></tr></thead><tbody>${rowsHtml}${footerHtml}</tbody></table>`
      : '<div style="color:var(--muted);font-size:0.78rem;padding:4px 0">No stage data yet</div>'
  }</div></td>`;

  runRow.after(breakdownRow);
}

export function checkHash() {
  const h = window.location.hash;
  const mIssue   = h.match(/^#issue\/([^/]+)\/(\d+)$/);
  const mProject = h.match(/^#project\/([^/]+)$/);
  if (mIssue)        openDrawer(decodeURIComponent(mIssue[1]), parseInt(mIssue[2], 10), null);
  else if (mProject) showProjectPanel(decodeURIComponent(mProject[1]));
}

export function initRunsPanel() {
  const stageFilter = document.getElementById('pr-stage-filter');
  const sortSel     = document.getElementById('pr-sort');
  const incFinished = document.getElementById('pr-include-finished');
  if (stageFilter) stageFilter.addEventListener('change', renderPrMonitor);
  if (sortSel)     sortSel.addEventListener('change', renderPrMonitor);
  if (incFinished) incFinished.addEventListener('change', () => {
    if (currentProject) loadPrMonitor(currentProject);
  });

  document.getElementById('project-panel-back').addEventListener('click', () => {
    history.pushState(null, '', window.location.pathname + window.location.search);
    showHome();
  });

  backdropEl.addEventListener('click', closeDrawer);
  document.getElementById('drawer-close').addEventListener('click', closeDrawer);

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDrawer();
  });

  document.addEventListener('click', e => {
    const link = e.target.closest('.timeline-link');
    if (link) {
      e.preventDefault();
      const project = link.dataset.project;
      const issue   = link.dataset.issue != null && link.dataset.issue !== ''
        ? parseInt(link.dataset.issue, 10) : null;
      const pr      = link.dataset.pr    != null && link.dataset.pr    !== ''
        ? parseInt(link.dataset.pr, 10)    : null;
      openDrawer(project, issue, pr);
      return;
    }

    const projLink = e.target.closest('.project-name-link');
    if (projLink) {
      e.preventDefault();
      showProjectPanel(projLink.dataset.project);
      return;
    }

    const toggleBtn = e.target.closest('.expand-toggle');
    if (toggleBtn) {
      e.stopPropagation();
      toggleExpandRow(toggleBtn.dataset.project, parseInt(toggleBtn.dataset.issue, 10), toggleBtn);
      return;
    }

    const runRow = e.target.closest('#runs-table-body tr[data-project]');
    if (runRow && !runRow.classList.contains('breakdown-row') && !e.target.closest('a') && !e.target.closest('.expand-toggle')) {
      const project = runRow.dataset.project;
      const issue   = runRow.dataset.issue !== '' ? parseInt(runRow.dataset.issue, 10) : null;
      const pr      = runRow.dataset.pr    !== '' ? parseInt(runRow.dataset.pr,    10) : null;
      openDrawer(project, issue, pr);
    }
  });

  window.addEventListener('hashchange', () => {
    const h = window.location.hash;
    const mIssue   = h.match(/^#issue\/([^/]+)\/(\d+)$/);
    const mProject = h.match(/^#project\/([^/]+)$/);
    if (mIssue)        openDrawer(decodeURIComponent(mIssue[1]), parseInt(mIssue[2], 10), null);
    else if (mProject) showProjectPanel(decodeURIComponent(mProject[1]));
    else { closeDrawer(); showHome(); }
  });
}
