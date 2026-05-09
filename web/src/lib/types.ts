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
