import { describe, it, expect } from 'vitest';
import { applyFilters, applySort } from './Queue';
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

describe('applyFilters', () => {
  const items: QueueItem[] = [
    item({ project: 'alpha', reason: 'stuck_label', loop_id: 'loop-1' }),
    item({ project: 'beta', reason: 'timeout', loop_id: 'loop-2' }),
    item({ project: 'alpha', reason: 'qa_fail_repeated', loop_id: null }),
  ];

  it('returns all items with no filter', () => {
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

  it('filters by loop', () => {
    const result = applyFilters(items, { loop: 'loop-1' });
    expect(result).toHaveLength(1);
    expect(result[0].loop_id).toBe('loop-1');
  });

  it('applies multiple filters together', () => {
    const result = applyFilters(items, { project: 'alpha', reason: 'stuck_label' });
    expect(result).toHaveLength(1);
  });

  it('returns empty array when no matches', () => {
    expect(applyFilters(items, { project: 'gamma' })).toHaveLength(0);
  });
});

describe('applySort', () => {
  const items: QueueItem[] = [
    item({ project: 'beta', age_seconds: 300, reason: 'timeout', kind: 'pr', number: 5 }),
    item({ project: 'alpha', age_seconds: 100, reason: 'stuck_label', kind: 'issue', number: 2 }),
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

  it('sorts by reason desc', () => {
    const result = applySort(items, 'reason', 'desc');
    expect(result[0].reason).toBe('timeout');
  });

  it('sorts by item (kind then number) asc', () => {
    const result = applySort(items, 'item', 'asc');
    expect(result[0].kind).toBe('issue');
    expect(result[0].number).toBe(1);
    expect(result[1].number).toBe(2);
    expect(result[2].kind).toBe('pr');
  });

  it('does not mutate the input array', () => {
    const input = [...items];
    applySort(items, 'age_seconds', 'asc');
    expect(items).toEqual(input);
  });
});
