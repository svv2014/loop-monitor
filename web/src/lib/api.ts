import type { ActionQueueItem, FailureContext } from './types';

const BASE = '';

export async function fetchActionQueue(): Promise<ActionQueueItem[]> {
  const res = await fetch(`${BASE}/api/action_queue`);
  if (!res.ok) throw new Error(`action_queue: ${res.status}`);
  return res.json();
}

export async function fetchFailureContext(
  project: string,
  kind: string,
  number: number,
): Promise<FailureContext> {
  const res = await fetch(
    `${BASE}/api/action_queue/${encodeURIComponent(project)}/${encodeURIComponent(kind)}/${number}/failure`,
  );
  if (!res.ok) throw new Error(`failure context: ${res.status}`);
  return res.json();
}
