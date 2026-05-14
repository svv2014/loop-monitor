// Thin fetch client mirroring the endpoints in static/js/api.js.
// When ?fixtures=1 is in the URL every function returns seeded data
// and makes zero network calls — verifiable in DevTools Network tab.
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
  ClaudeUsage,
  ScannerState,
  LogsResponse,
  IssueCostRow,
  FailureContext,
  CycleTimesResponse,
  CycleTimeAnalyticsResponse,
  SloConfig,
  CostTrend,
  TimelineResponse,
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
  const qs = p.size ? `?${p.toString()}` : '';
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

export async function fetchClaudeUsage(): Promise<ClaudeUsage> {
  if (isFixtureMode()) return fx.getFixtureClaudeUsage();
  return get<ClaudeUsage>('/api/claude_usage');
}

export async function fetchScannerState(): Promise<ScannerState> {
  if (isFixtureMode()) return fx.getFixtureScannerState();
  return get<ScannerState>('/api/scanner_state');
}

// Operator-configured role vocabulary. Pipeline-agnostic — the server reads
// config/roles.yaml (if present) and returns the list here. Falls back to the
// Loop defaults (po/dev/qa/reviewer/merge/judge) when no config exists.
export interface RoleConfig {
  id: string;
  label: string;
  color: string;
}

export const DEFAULT_ROLES: RoleConfig[] = [
  { id: 'po',       label: 'PO',       color: 'violet' },
  { id: 'dev',      label: 'Dev',      color: 'blue' },
  { id: 'qa',       label: 'QA',       color: 'amber' },
  { id: 'reviewer', label: 'Reviewer', color: 'pink' },
  { id: 'merge',    label: 'Merge',    color: 'green' },
  { id: 'judge',    label: 'Judge',    color: 'indigo' },
];

export async function fetchRoles(): Promise<RoleConfig[]> {
  if (isFixtureMode()) return DEFAULT_ROLES;
  try {
    const data = await get<{ roles: RoleConfig[] }>('/api/config/roles');
    return data.roles?.length ? data.roles : DEFAULT_ROLES;
  } catch {
    return DEFAULT_ROLES;
  }
}

export interface IssuesCostParams {
  project?: string;
  since?: string;
  limit?: number;
  offset?: number;
}

export async function fetchCostTrend(params: { days?: number; project?: string; priority?: string } = {}): Promise<CostTrend> {
  const p = new URLSearchParams();
  if (params.days != null)    p.set('days', String(params.days));
  if (params.project)         p.set('project', params.project);
  if (params.priority)        p.set('priority', params.priority);
  const qs = p.size ? `?${p.toString()}` : '';
  return get<CostTrend>(`/api/cost/trend${qs}`);
}

export async function fetchIssuesCost(params: IssuesCostParams = {}): Promise<IssueCostRow[]> {
  if (isFixtureMode()) return fx.getFixtureIssuesCost();
  const p = new URLSearchParams();
  if (params.project) p.set('project', params.project);
  if (params.since)   p.set('since', params.since);
  if (params.limit != null)  p.set('limit', String(params.limit));
  if (params.offset != null) p.set('offset', String(params.offset));
  const qs = p.size ? `?${p.toString()}` : '';
  return get<IssueCostRow[]>(`/api/issues/cost${qs}`);
}

export async function fetchFailureContext(
  project: string,
  kind: string,
  number: number,
): Promise<FailureContext> {
  return get<FailureContext>(
    `/api/action_queue/${encodeURIComponent(project)}/${encodeURIComponent(kind)}/${number}/failure`,
  );
}

export async function fetchCycleTimes(project: string): Promise<CycleTimesResponse> {
  return get<CycleTimesResponse>(`/api/projects/${encodeURIComponent(project)}/cycle_times`);
}

export async function fetchAnalyticsCycleTime(days = 30): Promise<CycleTimeAnalyticsResponse> {
  return get<CycleTimeAnalyticsResponse>(`/api/analytics/cycle_time?days=${days}`);
}

export async function fetchSlo(project: string): Promise<SloConfig> {
  return get<SloConfig>(`/api/projects/${encodeURIComponent(project)}/slo`);
}

export async function putSlo(project: string, body: { total_seconds: number | null; breach_grace_seconds: number }): Promise<SloConfig> {
  const res = await fetch(`/api/projects/${encodeURIComponent(project)}/slo`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<SloConfig>;
}

export class LogsDisabledError extends Error {
  constructor() { super('Logs are disabled. Set LOOPMON_EXPOSE_LOGS=1 or access via loopback.'); }
}

export async function fetchTimeline(slug: string, num: number, includeSkips = false): Promise<TimelineResponse> {
  const p = new URLSearchParams({ slug, num: String(num) });
  if (includeSkips) p.set('include_skips', 'true');
  return get<TimelineResponse>(`/api/timeline?${p.toString()}`);
}

export async function fetchLogs(handler: string, filter: string, tail: string): Promise<LogsResponse> {
  const params = new URLSearchParams({ handler, tail });
  if (filter) params.set('filter', filter);
  const res = await fetch(`/api/logs?${params.toString()}`);
  if (res.status === 403) throw new LogsDisabledError();
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || res.statusText);
  }
  return res.json() as Promise<LogsResponse>;
}
