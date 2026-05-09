// Typed API client — all fetch calls go through here. No fetch in screens or components.

export interface PipelineRun {
  id: number;
  project: string;
  issue_number: number | null;
  pr_number: number | null;
  title: string | null;
  outcome: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_duration_seconds: number | null;
  rework_count: number | null;
  total_bounty: number | null;
  created_at: string;
}

export interface PrMonitorRow {
  pr_number: number;
  title: string | null;
  branch: string | null;
  stage: string | null;
  time_in_stage_seconds: number | null;
  retry_count: number;
  last_event: string | null;
  last_event_at: string | null;
  github_url: string | null;
  is_finished: boolean;
  is_draft: boolean | null;
}

export interface FeedEvent {
  id: number;
  project: string;
  role: string;
  model: string;
  event_type: string;
  issue_number: number | null;
  pr_number: number | null;
  detail: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
  age_seconds: number | null;
  status: string;
}

export interface ActiveWorker {
  project: string;
  role: string;
  model: string;
  event_type: string;
  issue_number: number | null;
  pr_number: number | null;
  detail: string | null;
  created_at: string;
}

export interface ProjectStatusEntry {
  project: string;
  role: string;
  model: string;
  event_type: string;
  issue_number: number | null;
  pr_number: number | null;
  detail: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

const BASE = '';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const apiClient = {
  getProjectRuns: (project: string): Promise<PipelineRun[]> =>
    get(`/api/runs/${encodeURIComponent(project)}`),

  getProjectPrs: (project: string, includeFinished = false): Promise<PrMonitorRow[]> =>
    get(`/api/projects/${encodeURIComponent(project)}/prs?include_finished=${includeFinished}`),

  getFeed: (params?: { project?: string; role?: string; status?: string }): Promise<FeedEvent[]> => {
    const qs = new URLSearchParams();
    if (params?.role) qs.set('role', params.role);
    if (params?.status) qs.set('status', params.status);
    const query = qs.toString() ? `?${qs}` : '';
    return get(`/api/feed${query}`);
  },

  getActive: (): Promise<ActiveWorker[]> => get('/api/active'),

  getStatus: (): Promise<ProjectStatusEntry[]> => get('/api/status'),
};
