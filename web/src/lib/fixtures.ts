import type { PipelineHealth } from './types';

export function getFixturePipelineHealth(): PipelineHealth {
  const now = new Date().toISOString();
  return {
    scanner: {
      status: 'ok',
      last_tick_iso: now,
      interval_seconds: 60,
      detail: 'scanner running normally',
    },
    orchestrator: {
      status: 'stale',
      last_tick_iso: new Date(Date.now() - 180_000).toISOString(),
      interval_seconds: 60,
      detail: 'last invocation: 3 min ago',
    },
    event_queue: {
      status: 'down',
      last_tick_iso: null,
      interval_seconds: null,
      detail: 'connection refused at localhost:8765',
    },
  };
}
