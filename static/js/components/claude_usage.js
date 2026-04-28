import { escHtml, fmtDur } from '/js/utils.js';

let claudeUsageTimer = null;

export async function fetchClaudeUsage() {
  const section = document.getElementById('claude-usage-section');
  const body    = document.getElementById('claude-usage-body');
  let refreshSeconds = 300;
  try {
    const res  = await fetch('/api/claude_usage');
    const data = res.ok ? await res.json() : null;
    if (!data || !data.enabled) {
      section.classList.remove('visible');
    } else {
      refreshSeconds = data.refresh_seconds || 300;
      if (data.error) {
        body.innerHTML = `<span style="color:var(--muted);font-size:0.82rem">Claude usage unavailable: ${escHtml(data.error)}</span>`;
      } else {
        const pct = Math.min(100, Math.max(0, data.quota_pct || 0));
        const resetSecs = data.reset_at
          ? Math.max(0, Math.floor((new Date(data.reset_at).getTime() - Date.now()) / 1000))
          : null;
        const resetStr = resetSecs != null ? `resets in ${fmtDur(resetSecs)}` : '';
        body.innerHTML = `
          <div class="usage-bar"><div class="usage-fill" style="width:${pct}%"></div></div>
          <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--muted)">
            <span>${data.quota_used != null ? data.quota_used.toLocaleString() : '?'} / ${data.quota_limit != null ? data.quota_limit.toLocaleString() : '?'} &middot; ${pct}%</span>
            ${resetStr ? `<span>${escHtml(resetStr)}</span>` : ''}
          </div>
        `;
      }
      section.classList.add('visible');
    }
  } catch (e) {
    section.classList.remove('visible');
  }
  if (claudeUsageTimer) clearTimeout(claudeUsageTimer);
  claudeUsageTimer = setTimeout(fetchClaudeUsage, refreshSeconds * 1000);
}
