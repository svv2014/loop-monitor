import { escHtml } from '/js/utils.js';

const HANDLERS = [
  'scanner', 'reconciler', 'po-handler', 'dev-handler',
  'dev-rework-handler', 'review-handler', 'qa-handler', 'merge-handler',
];

function fmtBytes(n) {
  if (n == null) return '?';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function renderLines(lines) {
  if (!lines.length) return '<div style="color:var(--muted)">No matching lines.</div>';
  return lines.map(l => {
    const ts = l.ts ? `<span style="color:var(--muted)">${escHtml(l.ts)}</span> ` : '';
    const tag = l.handler ? `<span style="color:#7af">[${escHtml(l.handler)}]</span> ` : '';
    return `<div>${ts}${tag}${escHtml(l.msg ?? l.raw ?? '')}</div>`;
  }).join('');
}

async function refresh() {
  const handler = document.getElementById('logs-handler').value;
  const filter = document.getElementById('logs-filter').value;
  const tail = document.getElementById('logs-tail').value;
  const out = document.getElementById('logs-output');
  const banner = document.getElementById('logs-orphan-banner');
  const meta = document.getElementById('logs-meta');
  out.textContent = 'Loading…';
  banner.style.display = 'none';
  try {
    const params = new URLSearchParams({ handler, tail });
    if (filter) params.set('filter', filter);
    const res = await fetch(`/api/logs?${params.toString()}`);
    if (res.status === 403) {
      out.innerHTML = '<div style="color:#c44">Logs are disabled. Set LOOPMON_EXPOSE_LOGS=1 or access via loopback.</div>';
      meta.textContent = '';
      return;
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      out.innerHTML = `<div style="color:#c44">Error: ${escHtml(body.detail || res.statusText)}</div>`;
      meta.textContent = '';
      return;
    }
    const data = await res.json();
    meta.textContent = `${escHtml(data.path)} · disk=${fmtBytes(data.on_disk_bytes)} · fd=${fmtBytes(data.fd_bytes)}`;
    if (data.orphaned) {
      banner.innerHTML = `WARNING: ${escHtml(handler)} log appears orphaned (FD ${fmtBytes(data.fd_bytes)}, file ${fmtBytes(data.on_disk_bytes)}). See svv2014/loop#194.`;
      banner.style.display = 'block';
    }
    out.innerHTML = renderLines(data.lines);
  } catch (e) {
    out.innerHTML = `<div style="color:#c44">Fetch error: ${escHtml(String(e))}</div>`;
  }
}

export function initLogs() {
  const sel = document.getElementById('logs-handler');
  if (sel && !sel.options.length) {
    for (const h of HANDLERS) {
      const opt = document.createElement('option');
      opt.value = h;
      opt.textContent = h;
      sel.appendChild(opt);
    }
  }
  document.getElementById('logs-refresh').addEventListener('click', refresh);

  const overviewSelectors = [
    '#events-graph-section', 'main', '#claude-usage-section',
    '#charts-section', '#project-panel',
  ];
  document.querySelectorAll('#dashboard-tabs [data-dash-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.dashTab;
      const logsSection = document.getElementById('logs-section');
      const aq = document.getElementById('action-queue-section');
      if (tab === 'logs') {
        overviewSelectors.forEach(sel => {
          document.querySelectorAll(sel).forEach(el => { el.style.display = 'none'; });
        });
        if (aq) aq.style.display = 'none';
        logsSection.style.display = '';
      } else {
        logsSection.style.display = 'none';
      }
    });
  });
}
