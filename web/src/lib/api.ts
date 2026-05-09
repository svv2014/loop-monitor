// Thin fetch client over /api/*.
// Mirrors the endpoints called by static/js/api.js.
// When window.location.search contains fixtures=1 every function returns
// seeded fixture data and makes zero network calls.
import type {
  Worker,
  BoardEntry,
  Verdict,
  FeedItem,
  LoopEvent,
  StatusEntry,
  Project,
  EventsGraph,
  QueueItem,
  PipelineRun,
  PRMonitorEntry,
  Health,
  StatsActivity,
  StatsStage,
  StatsRework,
} from './types';
import * as fx from './fixtures';

function isFixtureMode(): boolean {
  return new URLSearchParams(window.location.search).has('fixtures');
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${url}`);
  return res.json() as Promise<T>;
}

export async function fetchActive(loop_id?: string): Promise<Worker[]> {
  if (isFixtureMode()) return fx.getFixtureActive();
  const qs = loop_id ? `?loop_id=${encodeURIComponent(loop_id)}` : '';
  return get<Worker[]>(`/api/active${qs}`);
}

export async function fetchBoard(): Promise<BoardEntry[]> {
  if (isFixtureMode()) return fx.getFixtureBoard();
  return get<BoardEntry[]>('/api/board');
}

export async function fetchVerdicts(): Promise<Verdict[]> {
  if (isFixtureMode()) return fx.getFixtureVerdicts();
  return get<Verdict[]>('/api/verdicts');
}

export interface FeedParams {
  loop_id?: string;
  role?: string;
  status?: string;
}
export async function fetchFeed(params: FeedParams = {}): Promise<FeedItem[]> {
  if (isFixtureMode()) return fx.getFixtureFeed();
  const p = new URLSearchParams();
  if (params.loop_id) p.set('loop_id', params.loop_id);
  if (params.role)    p.set('role', params.role);
  if (params.status)  p.set('status', params.status);
  const qs = p.toString() ? `?${p.toString()}` : '';
  return get<FeedItem[]>(`/api/feed${qs}`);
}

export async function fetchHistory(loop_id?: string): Promise<LoopEvent[]> {
  if (isFixtureMode()) return fx.getFixtureHistory();
  const qs = loop_id ? `?loop_id=${encodeURIComponent(loop_id)}` : '';
  return get<LoopEvent[]>(`/api/history${qs}`);
}

export async function fetchStatus(): Promise<StatusEntry[]> {
  if (isFixtureMode()) return fx.getFixtureStatus();
  return get<StatusEntry[]>('/api/status');
}

export async function fetchProjects(): Promise<Project[]> {
  if (isFixtureMode()) return fx.getFixtureProjects();
  return get<Project[]>('/api/projects');
}

export async function fetchEventsGraph(window_hours = 24): Promise<EventsGraph> {
  if (isFixtureMode()) return fx.getFixtureEventsGraph();
  return get<EventsGraph>(`/api/events_graph?window=${window_hours}`);
}

export async function fetchActionQueue(): Promise<QueueItem[]> {
  if (isFixtureMode()) return fx.getFixtureActionQueue();
  return get<QueueItem[]>('/api/action_queue');
}

export async function fetchRuns(project: string): Promise<PipelineRun[]> {
  if (isFixtureMode()) return fx.getFixtureRuns(project);
  return get<PipelineRun[]>(`/api/runs/${encodeURIComponent(project)}`);
}

export async function fetchPRMonitor(project: string): Promise<PRMonitorEntry[]> {
  if (isFixtureMode()) return fx.getFixturePRMonitor(project);
  return get<PRMonitorEntry[]>(`/api/projects/${encodeURIComponent(project)}/prs`);
}

export async function fetchHealth(): Promise<Health> {
  if (isFixtureMode()) return fx.getFixtureHealth();
  return get<Health>('/api/health');
}

export async function fetchStatsActivity(): Promise<StatsActivity[]> {
  if (isFixtureMode()) return fx.getFixtureStatsActivity();
  return get<StatsActivity[]>('/api/stats/activity');
}

export async function fetchStatsStages(): Promise<StatsStage[]> {
  if (isFixtureMode()) return fx.getFixtureStatsStages();
  return get<StatsStage[]>('/api/stats/stages');
}

export async function fetchStatsRework(): Promise<StatsRework[]> {
  if (isFixtureMode()) return fx.getFixtureStatsRework();
  return get<StatsRework[]>('/api/stats/rework');
}
