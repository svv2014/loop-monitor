export interface FailureContext {
  excerpt: string | null;
  model: string | null;
  run_id: string | null;
  retry_count: number;
  timestamp: string;
  github_comment_url: string | null;
  log_path: string | null;
  github_url: string | null;
}

export interface ActionQueueItem {
  project: string;
  kind: 'issue' | 'pr';
  number: number;
  title: string;
  stage: string;
  age_seconds: number;
  reason: string;
  loop_id: string;
  github_url: string | null;
}
