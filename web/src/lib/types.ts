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
