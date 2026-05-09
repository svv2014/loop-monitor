// Pure transform helpers ported from design/new-design/data.js.
// No side effects, no network calls, no imports from fixtures.
import type { LoopEvent, Worker } from './types';

export interface LeaderboardRow {
  key: string;
  verdicts: number;
  points: number;
}

export function buildLeaderboard(
  events: (LoopEvent & { points?: number; agent?: string })[],
  by: 'role' | 'agent' = 'role',
): LeaderboardRow[] {
  const map = new Map<string, LeaderboardRow>();
  for (const e of events) {
    const key = by === 'role' ? e.role : `${e.agent ?? ''}/${e.model ?? ''}`;
    if (!map.has(key)) map.set(key, { key, verdicts: 0, points: 0 });
    const row = map.get(key)!;
    const pts = e.points ?? 0;
    row.points += pts;
    if (pts > 0) row.verdicts += 1;
  }
  return Array.from(map.values()).sort((a, b) => b.points - a.points);
}

export interface ProjectStatusRow {
  id: string;
  lastEvent: string | null;
  lastTs: number;
  status: 'idle' | 'busy';
  points: number;
  totalEvents: number;
  busyWorker: Worker | null;
}

export function buildProjectStatus(
  events: (LoopEvent & { points?: number; ts?: number })[],
  workers: Worker[],
): ProjectStatusRow[] {
  const byProject = new Map<string, ProjectStatusRow>();

  for (const e of events) {
    if (!byProject.has(e.project)) {
      byProject.set(e.project, {
        id: e.project,
        lastEvent: null,
        lastTs: 0,
        status: 'idle',
        points: 0,
        totalEvents: 0,
        busyWorker: null,
      });
    }
    const row = byProject.get(e.project)!;
    row.totalEvents += 1;
    row.points += e.points ?? 0;
    const ts = e.ts ?? new Date(e.created_at).getTime();
    if (ts > row.lastTs) {
      row.lastTs = ts;
      row.lastEvent = e.event_type;
    }
  }

  for (const w of workers) {
    if (!byProject.has(w.project)) {
      byProject.set(w.project, {
        id: w.project,
        lastEvent: w.event_type,
        lastTs: new Date(w.created_at).getTime(),
        status: 'busy',
        points: 0,
        totalEvents: 0,
        busyWorker: w,
      });
    } else {
      const row = byProject.get(w.project)!;
      row.status = 'busy';
      row.busyWorker = w;
    }
  }

  return Array.from(byProject.values()).sort((a, b) => b.points - a.points);
}

const KNOWN_ROLES = ['po', 'dev', 'qa', 'reviewer', 'merge', 'judge'] as const;

export interface HourBucket {
  hour: number;
  counts: Record<string, number>;
  total: number;
}

export function build24hBuckets(
  events: (LoopEvent & { ts?: number })[],
): HourBucket[] {
  const buckets: HourBucket[] = Array.from({ length: 24 }, (_, i) => ({
    hour: i,
    counts: Object.fromEntries(KNOWN_ROLES.map((r) => [r, 0])),
    total: 0,
  }));
  const now = Date.now();
  for (const e of events) {
    const ts = e.ts ?? new Date(e.created_at).getTime();
    const hoursAgo = Math.floor((now - ts) / (60 * 60 * 1000));
    if (hoursAgo < 0 || hoursAgo >= 24) continue;
    const idx = 23 - hoursAgo;
    buckets[idx].counts[e.role] = (buckets[idx].counts[e.role] ?? 0) + 1;
    buckets[idx].total += 1;
  }
  return buckets;
}
