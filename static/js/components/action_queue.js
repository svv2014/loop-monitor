let currentItems = [];
let sortKey = 'age_seconds';
let sortDesc = true;

function fmtAge(seconds) {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

function ageColor(seconds) {
  if (seconds == null) return '';
  if (seconds > 86400) return 'color:#e44;font-weight:600';
  if (seconds > 21600) return 'color:#e9a000;font-weight:600';
  return 'color:#3c8;';
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function applyFilters(items) {
  const project = document.getElementById('aq-filter-project').value;
  const reason = document.getElementById('aq-filter-reason').value;
  const loop = document.getElementById('aq-filter-loop').value;
  return items.filter(it =>
    (!project || it.project === project) &&
    (!reason || it.reason === reason) &&
    (!loop || it.loop_id === loop)
  );
}

function sortItems(items) {
  const sorted = items.slice();
  sorted.sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (av < bv) return sortDesc ? 1 : -1;
    if (av > bv) return sortDesc ? -1 : 1;
    return 0;
  });
  return sorted;
}

function renderRows(items) {
  const tbody = document.getElementById('action-queue-body');
  if (!tbody) return;
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="no-workers">No items need your attention.</td></tr>';
    return;
  }
  tbody.innerHTML = items.map(it => `
    <tr>
      <td>${escapeHtml(it.project)}</td>
      <td>${escapeHtml(it.kind)}</td>
      <td>#${escapeHtml(it.number)}</td>
      <td>${escapeHtml(it.title)}</td>
      <td style="${ageColor(it.age_seconds)}">${fmtAge(it.age_seconds)}</td>
      <td>${escapeHtml(it.reason)}</td>
      <td>${escapeHtml(it.loop_id || '')}</td>
      <td>
        ${it.github_url ? `<a href="${escapeHtml(it.github_url)}" target="_blank" rel="noopener">GitHub</a>` : ''}
        ${it.kind === 'issue' ? ` · <a href="#runs/${encodeURIComponent(it.project)}">project</a>` : ''}
      </td>
    </tr>
  `).join('');
}

function refreshFilterOptions(items) {
  const projectSel = document.getElementById('aq-filter-project');
  const loopSel = document.getElementById('aq-filter-loop');
  const projects = [...new Set(items.map(i => i.project))].sort();
  const loops = [...new Set(items.map(i => i.loop_id).filter(Boolean))].sort();
  const ensureOptions = (sel, values) => {
    const current = sel.value;
    const existing = new Set(Array.from(sel.options).map(o => o.value));
    for (const v of values) {
      if (!existing.has(v)) {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        sel.appendChild(opt);
      }
    }
    sel.value = current;
  };
  ensureOptions(projectSel, projects);
  ensureOptions(loopSel, loops);
}

export function renderActionQueue(items) {
  currentItems = items || [];
  refreshFilterOptions(currentItems);
  const filtered = applyFilters(currentItems);
  renderRows(sortItems(filtered));
  const badge = document.getElementById('action-queue-badge');
  if (badge) {
    badge.textContent = String(currentItems.length);
    badge.style.display = currentItems.length > 0 ? '' : 'none';
  }
}

export function initActionQueue() {
  document.querySelectorAll('#dashboard-tabs [data-dash-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#dashboard-tabs [data-dash-tab]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.dashTab;
      const overviewSelectors = [
        '#events-graph-section', 'main', '#claude-usage-section',
        '#charts-section', '#project-panel',
      ];
      const aq = document.getElementById('action-queue-section');
      if (tab === 'action-queue') {
        overviewSelectors.forEach(sel => {
          document.querySelectorAll(sel).forEach(el => { el.dataset.prevDisplay = el.style.display; el.style.display = 'none'; });
        });
        aq.style.display = '';
      } else {
        overviewSelectors.forEach(sel => {
          document.querySelectorAll(sel).forEach(el => { el.style.display = el.dataset.prevDisplay || ''; });
        });
        aq.style.display = 'none';
      }
    });
  });

  ['aq-filter-project', 'aq-filter-reason', 'aq-filter-loop'].forEach(id => {
    document.getElementById(id).addEventListener('change', () => {
      renderRows(sortItems(applyFilters(currentItems)));
    });
  });

  document.querySelectorAll('#action-queue-table th[data-aq-sort]').forEach(th => {
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => {
      const key = th.dataset.aqSort;
      if (sortKey === key) {
        sortDesc = !sortDesc;
      } else {
        sortKey = key;
        sortDesc = true;
      }
      renderRows(sortItems(applyFilters(currentItems)));
    });
  });
}

export async function fetchActionQueue() {
  try {
    const res = await fetch('/api/action_queue');
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}
