import { describe, it, expect } from 'vitest';
import { applyFilters, applySort, PAGE_SIZE } from './Queue';
import type { QueueItem } from '../lib/types';

function item(overrides: Partial<QueueItem> = {}): QueueItem {
  return {
    project: 'proj-a',
    kind: 'issue',
    number: 1,
    title: 'Test',
    stage: 'dev',
    age_seconds: 120,
    reason: 'stuck_label',
    threshold_seconds: null,
    loop_id: null,
    github_url: null,
    ...overrides,
  };
}

// ── applyFilters ──────────────────────────────────────────────────────────────

describe('applyFilters', () => {
  const items: QueueItem[] = [
    item({ project: 'alpha', reason: 'stuck_label', loop_id: 'loop-1' }),
    item({ project: 'beta',  reason: 'timeout',        loop_id: 'loop-2' }),
    item({ project: 'alpha', reason: 'qa_fail_repeated', loop_id: null }),
  ];

  it('returns all items when no filter is set', () => {
    expect(applyFilters(items, {})).toHaveLength(3);
  });

  it('filters by project', () => {
    const result = applyFilters(items, { project: 'alpha' });
    expect(result).toHaveLength(2);
    expect(result.every(i => i.project === 'alpha')).toBe(true);
  });

  it('filters by reason', () => {
    const result = applyFilters(items, { reason: 'timeout' });
    expect(result).toHaveLength(1);
    expect(result[0].reason).toBe('timeout');
  });

  it('filters by loop_id', () => {
    const result = applyFilters(items, { loop: 'loop-1' });
    expect(result).toHaveLength(1);
    expect(result[0].loop_id).toBe('loop-1');
  });

  it('applies multiple filters together (AND)', () => {
    const result = applyFilters(items, { project: 'alpha', reason: 'stuck_label' });
    expect(result).toHaveLength(1);
  });

  it('returns empty when no items match', () => {
    expect(applyFilters(items, { project: 'gamma' })).toHaveLength(0);
  });
});

// ── applySort ─────────────────────────────────────────────────────────────────

describe('applySort', () => {
  const items: QueueItem[] = [
    item({ project: 'beta',  age_seconds: 300, reason: 'timeout',          kind: 'pr',    number: 5 }),
    item({ project: 'alpha', age_seconds: 100, reason: 'stuck_label',      kind: 'issue', number: 2 }),
    item({ project: 'alpha', age_seconds: 200, reason: 'qa_fail_repeated', kind: 'issue', number: 1 }),
  ];

  it('sorts by age_seconds asc', () => {
    const result = applySort(items, 'age_seconds', 'asc');
    expect(result.map(i => i.age_seconds)).toEqual([100, 200, 300]);
  });

  it('sorts by age_seconds desc', () => {
    const result = applySort(items, 'age_seconds', 'desc');
    expect(result.map(i => i.age_seconds)).toEqual([300, 200, 100]);
  });

  it('sorts by project asc', () => {
    const result = applySort(items, 'project', 'asc');
    expect(result[0].project).toBe('alpha');
    expect(result[2].project).toBe('beta');
  });

  it('sorts by project desc', () => {
    const result = applySort(items, 'project', 'desc');
    expect(result[0].project).toBe('beta');
  });

  it('sorts by reason alphabetically', () => {
    const result = applySort(items, 'reason', 'asc');
    expect(result[0].reason).toBe('qa_fail_repeated');
    expect(result[2].reason).toBe('timeout');
  });

  it('sorts by item (kind then number) asc', () => {
    const result = applySort(items, 'item', 'asc');
    expect(result[0]).toMatchObject({ kind: 'issue', number: 1 });
    expect(result[1]).toMatchObject({ kind: 'issue', number: 2 });
    expect(result[2]).toMatchObject({ kind: 'pr',    number: 5 });
  });

  it('sorts by item desc', () => {
    const result = applySort(items, 'item', 'desc');
    expect(result[0]).toMatchObject({ kind: 'pr', number: 5 });
  });

  it('does not mutate the input array', () => {
    const original = [...items];
    applySort(items, 'age_seconds', 'asc');
    expect(items).toEqual(original);
  });
});

// ── pagination helpers ────────────────────────────────────────────────────────

function makeItems(count: number): QueueItem[] {
  return Array.from({ length: count }, (_, i) =>
    item({ number: i + 1 }),
  );
}

describe('PAGE_SIZE', () => {
  it('is 20', () => {
    expect(PAGE_SIZE).toBe(20);
  });
});

describe('pagination slicing', () => {
  it('page 1 of 25 items renders 20 rows', () => {
    const all = makeItems(25);
    const page1 = all.slice(0, PAGE_SIZE);
    expect(page1).toHaveLength(20);
  });

  it('page 2 of 25 items renders 5 rows', () => {
    const all = makeItems(25);
    const page2 = all.slice(PAGE_SIZE, PAGE_SIZE * 2);
    expect(page2).toHaveLength(5);
  });

  it('page 1 of exactly 20 items renders 20 rows', () => {
    const all = makeItems(20);
    const page1 = all.slice(0, PAGE_SIZE);
    expect(page1).toHaveLength(20);
  });

  it('no second page when items <= 20', () => {
    const all = makeItems(20);
    const totalPages = Math.max(1, Math.ceil(all.length / PAGE_SIZE));
    expect(totalPages).toBe(1);
  });

  it('two pages when items = 21', () => {
    const all = makeItems(21);
    const totalPages = Math.max(1, Math.ceil(all.length / PAGE_SIZE));
    expect(totalPages).toBe(2);
  });

  it('clamps page to totalPages', () => {
    const all = makeItems(25);
    const totalPages = Math.max(1, Math.ceil(all.length / PAGE_SIZE));
    const clampedPage = Math.min(5, totalPages);
    expect(clampedPage).toBe(totalPages);
  });
});

