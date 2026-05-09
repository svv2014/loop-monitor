import { describe, expect, it } from 'vitest';
import type { FailureContext } from '../lib/types';

describe('FailureContext type', () => {
  it('accepts a full payload', () => {
    const ctx: FailureContext = {
      excerpt: 'ModuleNotFoundError: No module named foo',
      model: 'claude-sonnet-4-6',
      run_id: 'run-abc-123',
      retry_count: 2,
      timestamp: '2026-05-02T10:00:00Z',
      github_comment_url: 'https://github.com/org/repo/issues/1#issuecomment-1',
      log_path: '/var/log/loop/boba.log',
      github_url: 'https://github.com/org/repo/issues/1',
    };
    expect(ctx.retry_count).toBe(2);
    expect(ctx.excerpt).toContain('ModuleNotFoundError');
  });

  it('accepts an empty payload (no failure context)', () => {
    const ctx: FailureContext = {
      excerpt: null,
      model: null,
      run_id: null,
      retry_count: 0,
      timestamp: '',
      github_comment_url: null,
      log_path: null,
      github_url: null,
    };
    expect(ctx.excerpt).toBeNull();
  });
});
