import type { QueueItem } from './types';

export async function fetchActionQueue(): Promise<QueueItem[]> {
  const res = await fetch('/api/action_queue');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<QueueItem[]>;
}
