import { projectRepoMap } from '/js/state.js';

export const ROLES = ['Planner', 'Builder', 'Reviewer', 'Tester', 'Reviser'];

export const ROLE_EMOJI = {
  planner: '🗺️', builder: '🔨', reviewer: '🔍', tester: '🧪', reviser: '✏️',
};

export const EVENT_EMOJI = {
  start: '▶️', started: '▶️',
  done: '✅', complete: '✅', finished: '✅',
  error: '❌', fail: '❌', failed: '❌',
  rework: '🔄', retry: '🔄',
  idle: '💤',
  review: '🔍',
  test: '🧪',
  plan: '🗺️',
  build: '🔨',
};

export function escHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

export function fmtDur(s) {
  if (s == null) return '';
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60), r = s % 60;
  if (m < 60) return r ? `${m}m ${r}s` : `${m}m`;
  const h = Math.floor(m / 60), rm = m % 60;
  return `${h}h ${rm}m`;
}

export function timeAgo(isoStr) {
  if (!isoStr) return '';
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export function durFromIso(isoStr) {
  if (!isoStr) return '';
  const secs = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return `${h}h ${m}m`;
}

export function eventEmoji(eventType) {
  const key = (eventType || '').toLowerCase();
  for (const [k, v] of Object.entries(EVENT_EMOJI)) {
    if (key.includes(k)) return v;
  }
  return '📌';
}

export function statusFromEvent(eventType) {
  const k = (eventType || '').toLowerCase();
  if (k.includes('rework') || k.includes('retry')) return 'rework';
  if (k.includes('idle') || k.includes('done') || k.includes('complete') || k.includes('finish')) return 'idle';
  return 'busy';
}

export function modelShort(model) {
  if (!model) return '—';
  return model.replace(/^claude-/, '').replace(/-\d{8}$/, '');
}

export function ghLink(project, number, type = 'issue') {
  if (number == null) return '—';
  const repo = projectRepoMap[project];
  if (!repo) return `#${number}`;
  const url = `https://github.com/${repo}/${type}s/${number}`;
  return `<a class="gh-link" href="${url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">#${number}</a>`;
}

export function timelineLink(project, issue, pr) {
  if (issue != null) {
    return `<a class="timeline-link" href="#issue/${encodeURIComponent(project)}/${issue}" data-project="${escHtml(project)}" data-issue="${issue}">#${issue}</a>`;
  }
  if (pr != null) {
    return `<a class="timeline-link" href="#pr/${encodeURIComponent(project)}/${pr}" data-project="${escHtml(project)}" data-pr="${pr}">PR#${pr}</a>`;
  }
  return '—';
}
