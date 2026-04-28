import { fetchDashboard } from '/js/api.js';
import { setActiveWorkers, setStatusEntries, setProjectRepoMap } from '/js/state.js';
import { timeAgo } from '/js/utils.js';
import { renderBoard, initBoardTabs } from '/js/components/board.js';
import { renderFeed, renderHistory, renderVerdicts } from '/js/components/feed.js';
import { renderEventsGraph, initCharts, updateCharts, initGraphTooltip } from '/js/components/graph.js';
import { initVersionBadge, initLoopSelector } from '/js/components/header.js';
import { renderActive, renderAgents } from '/js/components/stats.js';
import { initRunsPanel, checkHash } from '/js/components/runs.js';
import { fetchClaudeUsage } from '/js/components/claude_usage.js';

async function fetchAll() {
  try {
    const data = await fetchDashboard();
    if (!data) return;

    const { board, feed, status, verdicts, active, hist,
            activity, stages, rework, projects, eventsGraph } = data;

    if (projects.length) {
      setProjectRepoMap(Object.fromEntries(projects.map(p => [p.project, p.repo])));
    }

    setActiveWorkers(active);
    setStatusEntries(status);

    renderEventsGraph(eventsGraph);
    renderActive(active);
    renderBoard(board);
    renderAgents();
    renderFeed(feed);
    renderHistory(hist);
    renderVerdicts(verdicts);
    updateCharts(activity, board, stages, rework);

    document.getElementById('last-update').textContent = 'Updated ' + timeAgo(new Date().toISOString());
  } catch (e) {
    console.error('Fetch error:', e);
  }
}

initCharts();
initBoardTabs();
initRunsPanel();
initGraphTooltip();
initVersionBadge();
initLoopSelector(fetchAll);
fetchAll();
setInterval(fetchAll, 5000);
fetchClaudeUsage();
checkHash();
