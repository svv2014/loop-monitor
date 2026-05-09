import type { PipelineHealth } from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';

export async function fetchPipelineHealth(): Promise<PipelineHealth> {
  const res = await fetch(`${BASE}/api/health/pipeline`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
