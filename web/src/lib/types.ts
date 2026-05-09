export type SubsystemStatus = 'ok' | 'stale' | 'down';

export interface SubsystemHealth {
  status: SubsystemStatus;
  last_tick_iso: string | null;
  interval_seconds: number | null;
  detail: string;
}

export interface PipelineHealth {
  scanner: SubsystemHealth;
  orchestrator: SubsystemHealth;
  event_queue: SubsystemHealth;
}
