import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchFeed } from './api';

// Stub window so isFixtureMode() doesn't throw in node env
beforeEach(() => {
  vi.stubGlobal('window', { location: { search: '' } });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve([]),
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ── fetchFeed limit param ─────────────────────────────────────────────────────

describe('fetchFeed limit param', () => {
  it('includes limit in query string when provided', async () => {
    await fetchFeed({ limit: 200 });
    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('limit=200');
  });

  it('omits limit from query string when not provided', async () => {
    await fetchFeed({});
    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).not.toContain('limit');
  });

  it('omits limit from query string when limit is undefined', async () => {
    await fetchFeed({ limit: undefined });
    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).not.toContain('limit');
  });

  it('combines limit with other params correctly', async () => {
    await fetchFeed({ role: 'dev', limit: 50 });
    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('role=dev');
    expect(url).toContain('limit=50');
  });

  it('calls /api/feed endpoint', async () => {
    await fetchFeed({});
    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toBe('/api/feed');
  });

  it('appends query string when params are present', async () => {
    await fetchFeed({ limit: 10 });
    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toBe('/api/feed?limit=10');
  });
});
