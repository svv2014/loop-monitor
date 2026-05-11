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
  TokenSpend,
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

export interface IssuesCostParams {
  project?: string;
  since?: string;
  limit?: number;
  offset?: number;
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

export async function fetchTokenSpend(): Promise<TokenSpend> {
  if (isFixtureMode()) return fx.getFixtureTokenSpend();
  return get<TokenSpend>('/api/token_spend');
}

export class LogsDisabledError extends Error {
  constructor() { super('Logs are disabled. Set LOOPMON_EXPOSE_LOGS=1 or access via loopback.'); }
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
