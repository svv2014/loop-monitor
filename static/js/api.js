import { currentLoopId } from '/js/state.js';

function buildFeedUrl() {
  const params = new URLSearchParams();
  if (currentLoopId) params.set('loop_id', currentLoopId);
  const roleEl   = document.getElementById('feed-role-filter');
  const statusEl = document.getElementById('feed-status-filter');
  if (roleEl   && roleEl.value)   params.set('role',   roleEl.value);
  if (statusEl && statusEl.value) params.set('status', statusEl.value);
  const qs = params.toString();
  return qs ? `/api/feed?${qs}` : '/api/feed';
}

export async function fetchDashboard() {
  const loopParam = currentLoopId ? `?loop_id=${encodeURIComponent(currentLoopId)}` : '';
  const [boardRes, feedRes, statusRes, verdictsRes, activeRes, historyRes,
         activityRes, stagesRes, reworkRes, projectsRes, eventsGraphRes] = await Promise.all([
    fetch('/api/board'),
    fetch(buildFeedUrl()),
    fetch('/api/status'),
    fetch('/api/verdicts'),
    fetch('/api/active'),
    fetch(`/api/history${loopParam}`),
    fetch('/api/stats/activity'),
    fetch('/api/stats/stages'),
    fetch('/api/stats/rework'),
    fetch('/api/projects'),
    fetch('/api/events_graph?window=24'),
  ]);

  if (!boardRes.ok || !feedRes.ok || !statusRes.ok || !verdictsRes.ok ||
      !activeRes.ok || !historyRes.ok) return null;

  const [board, feed, status, verdicts, active, hist,
         activity, stages, rework, projects, eventsGraph] = await Promise.all([
    boardRes.json(),
    feedRes.json(),
    statusRes.json(),
    verdictsRes.json(),
    activeRes.json(),
    historyRes.json(),
    activityRes.ok ? activityRes.json() : Promise.resolve([]),
    stagesRes.ok   ? stagesRes.json()   : Promise.resolve([]),
    reworkRes.ok   ? reworkRes.json()   : Promise.resolve([]),
    projectsRes.ok ? projectsRes.json() : Promise.resolve([]),
    eventsGraphRes.ok ? eventsGraphRes.json() : Promise.resolve(null),
  ]);

  return { board, feed, status, verdicts, active, hist, activity, stages, rework, projects, eventsGraph };
}
