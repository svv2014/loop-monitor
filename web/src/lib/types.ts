// TS interfaces mirroring server/routes payload shapes.
// Read from server/routes/*.py — do not invent fields.

export interface Worker {
  project: string;
  role: string;
  model: string | null;
  event_type: string;
  issue_number: number | null;
  pr_number: number | null;
  detail: string | null;
  created_at: string;
}

export interface BoardEntry {
  project: string;
  role: string;
  model: string | null;
  total_points: number;
  verdict_count: number;
}

export interface Verdict {
  id: number;
  project: string;
  role: string;
  model: string | null;
  points: number;
  reason: string | null;
  created_at: string;
}

export interface FeedItem {
  id: number;
  project: string;
  role: string;
  model: string | null;
  event_type: string;
  issue_number: number | null;
  pr_number: number | null;
  detail: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
  age_seconds: number | null;
  status: string;
}

export interface LoopEvent {
  id: number;
  project: string;
  role: string;
  model: string | null;
  event_type: string;
  issue_number: number | null;
  pr_number: number | null;
  detail: string | null;
  created_at: string;
  completed_at?: string;
  started_at?: string | null;
  duration_seconds?: number | null;
  points?: number | null;
}

export interface StatusEntry {
  project: string;
  role: string;
  model: string | null;
  event_type: string;
  issue_number: number | null;
  pr_number: number | null;
  detail: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface Project {
  project: string;
  repo: string;
}

export interface EventsGraphBucket {
  hour: string;
  role: string;
  count: number;
}

export interface EventsGraph {
  window_hours: number;
  buckets: EventsGraphBucket[];
}

export interface QueueItem {
  project: string;
  kind: 'issue' | 'pr';
  number: number;
  title: string;
  stage: string;
  age_seconds: number;
  reason: 'stuck_label' | 'timeout' | 'qa_fail_repeated';
  threshold_seconds: number | null;
  loop_id: string | null;
  github_url: string | null;
}

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
  rework_count: number;
  total_bounty: number | null;
  created_at: string;
}

export interface PRMonitorEntry {
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

export interface Health {
  status: string;
  monitor_version: string;
  git_sha: string;
  supported_bounty_api: string;
  core_version_counts: Record<string, number>;
  loop_ids: string[];
}

export interface StatsActivity {
  date: string;
  project: string;
  n: number;
}

export interface StatsStage {
  stage: string;
  avg_seconds: number;
  count: number;
}

export interface StatsRework {
  project: string;
  rework_starts: number;
  review_dones: number;
}

export interface ClaudeUsage {
  enabled: boolean;
  quota_used?: number | null;
  quota_limit?: number | null;
  quota_pct?: number | null;
  reset_at?: string | null;
  cache_hit_pct?: number | null;
  refresh_seconds?: number | null;
  error?: string | null;
}

export interface StageInfo {
  in_flight: number;
  cap: number | null;
}

export interface RetryRow {
  project: string;
  kind: string;
  number: number;
  stage: string;
  count: number;
  max: number;
}

export interface ScannerState {
  stages: Record<string, StageInfo>;
  retries: RetryRow[];
}

export interface LogLine {
  ts?: string;
  handler?: string;
  msg?: string;
  raw?: string;
}

export interface LogsResponse {
  path: string;
  on_disk_bytes: number;
  fd_bytes: number | null;
  orphaned: boolean;
  lines: LogLine[];
}

export interface FailureContext {
  excerpt: string | null;
  model: string | null;
  run_id: string | null;
  retry_count: number;
  timestamp: string | null;
  github_comment_url: string | null;
  log_path: string | null;
}

export interface StageStat {
  p50_seconds: number;
  p90_seconds: number;
  sample_size: number;
}

export interface PercentileStat {
  median_seconds: number;
  p90_seconds: number;
  sample_size: number;
  most_recent_seconds: number;
}

export interface CycleTimesResponse {
  total_duration: PercentileStat | null;
  issue_lifetime: PercentileStat | null;
  pr_lifetime: PercentileStat | null;
  stages: Record<string, StageStat>;
  rework_rate: number | null;
}

export interface SloConfig {
  slug: string;
  total_seconds: number | null;
  breach_grace_seconds: number;
  updated_at: number | null;
}

export interface CycleTimeStage {
  stage: string;
  p50: number;
  p75: number;
  p95: number;
  count: number;
}

export interface CycleTimePct {
  p50: number;
  p75: number;
  p95: number;
  count: number;
}

export interface CycleTimeAnalyticsResponse {
  stages: CycleTimeStage[];
  lead_time: CycleTimePct | null;
}

export interface IssueCostRow {
  project: string;
  issue_number: number;
  priority: string;
  state: string;
  rework_factor: number;
  total_points: number;
  stranded_seconds: number | null;
  actual_runs: number;
  last_event_at: string | null;
  github_url: string | null;
}

export interface QualityVerdicts {
  clean: number;
  light_rework: number;
  heavy_rework: number;
  blocked: number;
}

export interface QualityStageFailure {
  stage: string;
  fail_rate: number;
  sample: number;
}

export interface QualityReworkBucket {
  label: string;
  count: number;
}

export interface QualityReworkDist {
  p50: number | null;
  p75: number | null;
  p95: number | null;
  buckets: QualityReworkBucket[];
}

export interface QualityFailureTypes {
  po_failed: number;
  dev_failed: number;
  qa_fail: number;
  review_failed: number;
  merge_failed: number;
}

export interface QualityDailyRate {
  date: string;
  rate: number | null;
}

export interface QualityAnalyticsResponse {
  verdicts: QualityVerdicts;
  qa_pass_rate: number | null;
  qa_pass_rate_daily: QualityDailyRate[];
  stage_failure: QualityStageFailure[];
  rework_dist: QualityReworkDist;
  failure_types: QualityFailureTypes;
}

export interface CostTrendBucket {
  date: string;
  median_rework_factor: number | null;
  issue_count: number;
}

export interface CostTimeseriesTopIssue {
  project: string;
  issue_number: number;
  rework_events: number;
}

export interface CostTimeseriesBucket {
  date: string;
  total_rework_events: number;
  by_stage: {
    po_failed: number;
    dev_rework: number;
    qa_fail: number;
    review_reject: number;
  };
  top_issues: CostTimeseriesTopIssue[];
}

export interface CostTimeseries {
  window_days: number;
  buckets: CostTimeseriesBucket[];
}

export interface CostTrend {
  window_days: number;
  today: {
    median_rework_factor: number | null;
    issue_count: number;
  };
  vs_7d: number | null;
  vs_30d: number | null;
  trend: 'improving' | 'degrading' | 'stable';
  buckets: CostTrendBucket[];
}
