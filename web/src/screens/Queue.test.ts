import { describe, it, expect } from 'vitest';
import { applyFilters, applySort, paginateItems, parsePageFromHash, buildHashWithPage, PAGE_SIZE } from './Queue';
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

// ── paginateItems ─────────────────────────────────────────────────────────────

describe('paginateItems', () => {
  // Build 25 distinct items
  const twentyFive = Array.from({ length: 25 }, (_, i) =>
    item({ number: i + 1, age_seconds: i }),
  );

  it('PAGE_SIZE is 20', () => {
    expect(PAGE_SIZE).toBe(20);
  });

  it('returns 20 items on page 1 when there are 25 items', () => {
    const { pageItems, totalPages } = paginateItems(twentyFive, 1);
    expect(pageItems).toHaveLength(20);
    expect(totalPages).toBe(2);
  });

  it('returns 5 items on page 2 when there are 25 items', () => {
    const { pageItems } = paginateItems(twentyFive, 2);
    expect(pageItems).toHaveLength(5);
  });

  it('clamps page to 1 when page < 1', () => {
    const { clampedPage, pageItems } = paginateItems(twentyFive, 0);
    expect(clampedPage).toBe(1);
    expect(pageItems).toHaveLength(20);
  });

  it('clamps page to totalPages when page exceeds totalPages', () => {
    const { clampedPage, pageItems } = paginateItems(twentyFive, 99);
    expect(clampedPage).toBe(2);
    expect(pageItems).toHaveLength(5);
  });

  it('returns all items on page 1 when items <= PAGE_SIZE', () => {
    const five = twentyFive.slice(0, 5);
    const { pageItems, totalPages } = paginateItems(five, 1);
    expect(pageItems).toHaveLength(5);
    expect(totalPages).toBe(1);
  });

  it('returns empty array when items is empty', () => {
    const { pageItems, totalPages } = paginateItems([], 1);
    expect(pageItems).toHaveLength(0);
    expect(totalPages).toBe(1);
  });
});

// ── parsePageFromHash / buildHashWithPage ─────────────────────────────────────

describe('parsePageFromHash', () => {
  it('returns 1 when hash has no page param', () => {
    expect(parsePageFromHash('#queue')).toBe(1);
  });

  it('returns the page number when hash contains page param', () => {
    expect(parsePageFromHash('#queue?page=3')).toBe(3);
  });

  it('returns 1 for invalid page values', () => {
    expect(parsePageFromHash('#queue?page=abc')).toBe(1);
  });

  it('returns 1 for page=0', () => {
    expect(parsePageFromHash('#queue?page=0')).toBe(1);
  });
});

describe('buildHashWithPage', () => {
  it('adds page param for page > 1', () => {
    expect(buildHashWithPage('#queue', 2)).toBe('#queue?page=2');
  });

  it('removes page param for page 1', () => {
    expect(buildHashWithPage('#queue?page=3', 1)).toBe('#queue');
  });

  it('preserves other query params alongside page', () => {
    const result = buildHashWithPage('#queue?foo=bar', 4);
    const params = new URLSearchParams(result.split('?')[1]);
    expect(params.get('page')).toBe('4');
    expect(params.get('foo')).toBe('bar');
  });
});
