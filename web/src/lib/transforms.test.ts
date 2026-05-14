import { describe, it, expect, vi, afterEach } from 'vitest';
import { buildLeaderboard, buildProjectStatus, build24hBuckets } from './transforms';
import { relTime, durationFmt, absoluteUtc, matchesProjectFilter } from './utils';
import type { LoopEvent, Worker } from './types';

type ExtLoopEvent = LoopEvent & { points?: number; agent?: string; ts?: number };

function makeEvent(overrides: Partial<ExtLoopEvent> = {}): ExtLoopEvent {
  return {
    id: 1,
    project: 'loop',
    role: 'dev',
    model: 'sonnet-4-6',
    event_type: 'dev_done',
    issue_number: 1,
    pr_number: null,
    detail: null,
    created_at: new Date().toISOString(),
    points: 0,
    ...overrides,
  };
}

function makeWorker(overrides: Partial<Worker> = {}): Worker {
  return {
    project: 'loop',
    role: 'dev',
    model: 'sonnet-4-6',
    event_type: 'dev_start',
    issue_number: 1,
    pr_number: null,
    detail: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

// ── relTime ───────────────────────────────────────────────────────────────────

describe('relTime', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('returns seconds with ago suffix', () => {
    vi.spyOn(Date, 'now').mockReturnValue(30_000);
    expect(relTime(0)).toBe('30s ago');
  });

  it('returns minutes with ago suffix', () => {
    vi.spyOn(Date, 'now').mockReturnValue(5 * 60 * 1000);
    expect(relTime(0)).toBe('5m ago');
  });

  it('returns hours with ago suffix', () => {
    vi.spyOn(Date, 'now').mockReturnValue(3 * 3600 * 1000);
    expect(relTime(0)).toBe('3h ago');
  });

  it('returns days with ago suffix', () => {
    vi.spyOn(Date, 'now').mockReturnValue(2 * 86400 * 1000);
    expect(relTime(0)).toBe('2d ago');
  });
});

// ── durationFmt ───────────────────────────────────────────────────────────────

describe('durationFmt', () => {
  it('formats seconds', () => {
    expect(durationFmt(45_000)).toBe('45s');
  });

  it('formats minutes and seconds', () => {
    expect(durationFmt(5 * 60 * 1000 + 30 * 1000)).toBe('5m 30s');
  });

  it('pads seconds to two digits', () => {
    expect(durationFmt(60_000 + 5_000)).toBe('1m 05s');
  });

  it('formats hours and minutes', () => {
    expect(durationFmt(2 * 3600 * 1000 + 15 * 60 * 1000)).toBe('2h 15m');
  });
});

// ── absoluteUtc ───────────────────────────────────────────────────────────────

describe('absoluteUtc', () => {
  it('returns ISO-8601 UTC string for epoch 0', () => {
    expect(absoluteUtc(0)).toBe(new Date(0).toISOString());
  });

  it('returns ISO-8601 UTC string for a known timestamp', () => {
    const ts = 1_715_565_366_000;
    expect(absoluteUtc(ts)).toBe(new Date(ts).toISOString());
  });
});

// ── buildLeaderboard ──────────────────────────────────────────────────────────

describe('buildLeaderboard', () => {
  it('aggregates points and verdicts by role', () => {
    const events = [
      makeEvent({ role: 'dev', points: 3 }),
      makeEvent({ role: 'dev', points: 2 }),
      makeEvent({ role: 'qa',  points: 5 }),
      makeEvent({ role: 'dev', points: 0 }),
    ];
    const rows = buildLeaderboard(events, 'role');
    const dev = rows.find((r) => r.key === 'dev')!;
    const qa  = rows.find((r) => r.key === 'qa')!;
    expect(dev.points).toBe(5);
    expect(dev.verdicts).toBe(2);
    expect(qa.points).toBe(5);
    expect(qa.verdicts).toBe(1);
  });

  it('returns rows sorted descending by points', () => {
    const events = [
      makeEvent({ role: 'po',  points: 1 }),
      makeEvent({ role: 'dev', points: 10 }),
      makeEvent({ role: 'qa',  points: 5 }),
    ];
    const rows = buildLeaderboard(events, 'role');
    expect(rows[0].key).toBe('dev');
    expect(rows[1].key).toBe('qa');
    expect(rows[2].key).toBe('po');
  });

  it('aggregates by agent/model when by=agent', () => {
    const events = [
      makeEvent({ agent: 'claude', model: 'sonnet-4-6', points: 3 }),
      makeEvent({ agent: 'claude', model: 'sonnet-4-6', points: 2 }),
      makeEvent({ agent: 'gpt',    model: 'gpt-5',      points: 7 }),
    ];
    const rows = buildLeaderboard(events, 'agent');
    expect(rows[0].key).toBe('gpt/gpt-5');
    expect(rows[0].points).toBe(7);
    expect(rows[1].points).toBe(5);
  });

  it('ignores events with zero points in verdict count', () => {
    const events = [
      makeEvent({ role: 'merge', points: 0 }),
      makeEvent({ role: 'merge', points: 0 }),
    ];
    const rows = buildLeaderboard(events, 'role');
    expect(rows[0].verdicts).toBe(0);
  });

  it('returns empty array for empty input', () => {
    expect(buildLeaderboard([])).toEqual([]);
  });
});

// ── buildProjectStatus ────────────────────────────────────────────────────────

describe('buildProjectStatus', () => {
  it('marks projects with a busy worker as busy', () => {
    const events = [makeEvent({ project: 'loop', points: 5 })];
    const workers = [makeWorker({ project: 'loop' })];
    const rows = buildProjectStatus(events, workers);
    const loop = rows.find((r) => r.id === 'loop')!;
    expect(loop.status).toBe('busy');
    expect(loop.busyWorker).toBeTruthy();
  });

  it('marks projects with no busy worker as idle', () => {
    const events = [makeEvent({ project: 'loop', points: 3 })];
    const rows = buildProjectStatus(events, []);
    expect(rows[0].status).toBe('idle');
    expect(rows[0].busyWorker).toBeNull();
  });

  it('accumulates points across multiple events', () => {
    const events = [
      makeEvent({ project: 'loop', points: 2 }),
      makeEvent({ project: 'loop', points: 3 }),
      makeEvent({ project: 'loop', points: 0 }),
    ];
    const rows = buildProjectStatus(events, []);
    expect(rows[0].points).toBe(5);
    expect(rows[0].totalEvents).toBe(3);
  });

  it('tracks the most recent event_type as lastEvent', () => {
    const old    = makeEvent({ project: 'loop', event_type: 'dev_start', ts: Date.now() - 10_000 });
    const recent = makeEvent({ project: 'loop', event_type: 'dev_done',  ts: Date.now() });
    const rows = buildProjectStatus([old, recent], []);
    expect(rows[0].lastEvent).toBe('dev_done');
  });

  it('sorts by points descending', () => {
    const events = [
      makeEvent({ project: 'alpha', points: 1 }),
      makeEvent({ project: 'beta',  points: 10 }),
    ];
    const rows = buildProjectStatus(events, []);
    expect(rows[0].id).toBe('beta');
  });
});

// ── build24hBuckets ───────────────────────────────────────────────────────────

describe('build24hBuckets', () => {
  it('returns exactly 24 buckets', () => {
    expect(build24hBuckets([])).toHaveLength(24);
  });

  it('places a recent event in the last bucket (index 23)', () => {
    const now = Date.now();
    const events = [makeEvent({ role: 'dev', ts: now - 5 * 60 * 1000 })];
    const buckets = build24hBuckets(events);
    expect(buckets[23].counts['dev']).toBe(1);
    expect(buckets[23].total).toBe(1);
  });

  it('places an event from ~23h ago in bucket 0', () => {
    const ts = Date.now() - 23 * 60 * 60 * 1000 - 60_000;
    const events = [makeEvent({ role: 'qa', ts })];
    const buckets = build24hBuckets(events);
    expect(buckets[0].counts['qa']).toBe(1);
  });

  it('ignores events older than 24h', () => {
    const old = makeEvent({ ts: Date.now() - 25 * 3_600_000 });
    const buckets = build24hBuckets([old]);
    const total = buckets.reduce((s, b) => s + b.total, 0);
    expect(total).toBe(0);
  });

  it('accumulates multiple events in the same bucket', () => {
    const now = Date.now();
    const events = [
      makeEvent({ role: 'po',  ts: now - 1000 }),
      makeEvent({ role: 'dev', ts: now - 2000 }),
      makeEvent({ role: 'qa',  ts: now - 3000 }),
    ];
    const buckets = build24hBuckets(events);
    expect(buckets[23].total).toBe(3);
  });
});

// ── matchesProjectFilter ──────────────────────────────────────────────────────

describe('matchesProjectFilter', () => {
  it('returns true when filter is null (no filter active)', () => {
    expect(matchesProjectFilter('loop-monitor', null)).toBe(true);
  });

  it('returns true when filter is undefined', () => {
    expect(matchesProjectFilter('loop-monitor', undefined)).toBe(true);
  });

  it('returns true when project matches the filter exactly', () => {
    expect(matchesProjectFilter('loop-monitor', 'loop-monitor')).toBe(true);
  });

  it('returns false when project does not match the filter', () => {
    expect(matchesProjectFilter('other-project', 'loop-monitor')).toBe(false);
  });

  it('is case-sensitive', () => {
    expect(matchesProjectFilter('Loop-Monitor', 'loop-monitor')).toBe(false);
  });
});
