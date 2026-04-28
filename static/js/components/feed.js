import { escHtml, fmtDur, timeAgo, eventEmoji, timelineLink } from '/js/utils.js';

export function renderFeed(items) {
  const list = document.getElementById('feed-list');
  if (!items.length) {
    list.innerHTML = '<div class="empty-state">No activity yet</div>';
    return;
  }
  list.innerHTML = items.map(item => {
    const emoji = eventEmoji(item.event_type);
    const role = (item.role || '').charAt(0).toUpperCase() + (item.role || '').slice(1);
    const when = item.age_seconds != null ? fmtDur(item.age_seconds) + ' ago' : timeAgo(item.created_at);
    const taskHtml = item.issue_number != null
      ? ' ' + timelineLink(item.project, item.issue_number, null)
      : item.pr_number != null
        ? ' ' + timelineLink(item.project, null, item.pr_number)
        : '';
    const detail = item.detail ? ` — ${escHtml(item.detail)}` : '';
    return `
      <div class="feed-item">
        <span class="feed-emoji">${emoji}</span>
        <div>
          <span class="feed-role">${escHtml(role)}</span>
          <span style="color:var(--text)"> ${escHtml(item.event_type)}${taskHtml}${detail}</span>
          <div class="feed-meta">${escHtml(item.project || '')} · ${escHtml(when)}</div>
        </div>
      </div>
    `;
  }).join('');
}

export function renderHistory(items) {
  const list = document.getElementById('history-list');
  if (!items.length) {
    list.innerHTML = '<div class="empty-state">No completed jobs yet</div>';
    return;
  }
  list.innerHTML = items.map(item => {
    const role = (item.role || '').charAt(0).toUpperCase() + (item.role || '').slice(1);
    const when = timeAgo(item.completed_at);
    const taskHtml = item.issue_number != null
      ? ' ' + timelineLink(item.project, item.issue_number, null)
      : item.pr_number != null
        ? ' ' + timelineLink(item.project, null, item.pr_number)
        : '';
    const dur = item.duration_seconds != null ? fmtDur(item.duration_seconds) : null;
    const pts = item.points != null ? item.points : null;
    const ptsClass = pts == null ? '' : pts > 0 ? 'pos' : 'neg';
    const model = item.model
      ? `<span style="color:var(--muted);font-size:0.68rem"> · ${escHtml(item.model.replace(/^claude-/, '').replace(/-\d{8}$/, ''))}</span>`
      : '';
    const failed = (item.event_type || '').includes('fail');
    return `
      <div class="verdict-item">
        <div class="verdict-header">
          <span class="verdict-role">${failed ? '❌' : '✅'} ${escHtml(item.project || '')} · ${escHtml(role)}${model}</span>
          ${pts != null ? `<span class="verdict-pts ${ptsClass}">${pts > 0 ? '+' : ''}${pts} pts</span>` : ''}
        </div>
        <div style="font-size:0.75rem;color:var(--accent2);margin:2px 0">${escHtml(item.event_type)}${taskHtml}</div>
        <div class="feed-meta">${escHtml(when)}${dur ? ' · ' + escHtml(dur) : ''}</div>
      </div>
    `;
  }).join('');
}

export function renderVerdicts(verdicts) {
  const list = document.getElementById('verdict-list');
  if (!verdicts.length) {
    list.innerHTML = '<div class="empty-state">No verdicts yet</div>';
    return;
  }
  list.innerHTML = verdicts.map(item => {
    const role = (item.role || '').charAt(0).toUpperCase() + (item.role || '').slice(1);
    const pts = item.points != null ? item.points : null;
    const reason = (item.reason || '').replace(/^auto:\s*/, '');
    const ptsClass = pts == null ? 'zero' : pts > 0 ? 'pos' : pts < 0 ? 'neg' : 'zero';
    const ptsLabel = pts == null ? '?' : (pts >= 0 ? '+' + pts : pts) + ' pts';
    return `
      <div class="verdict-item">
        <div class="verdict-header">
          <span class="verdict-role">${escHtml(item.project || '')} · ${escHtml(role)}</span>
          <span class="verdict-pts ${ptsClass}">${ptsLabel}</span>
        </div>
        ${reason ? `<div class="verdict-reason">${escHtml(reason)}</div>` : ''}
        <div class="feed-meta" style="margin-top:3px">${escHtml(timeAgo(item.created_at))}</div>
      </div>
    `;
  }).join('');
}
