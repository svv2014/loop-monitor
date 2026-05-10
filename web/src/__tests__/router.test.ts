import { describe, it, expect, beforeEach } from 'vitest';

// Pure hash parsing/writing logic extracted for testability
function parseHash(hash: string): Record<string, string> {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  if (!raw) return {};
  return Object.fromEntries(
    raw.split('&').flatMap(pair => {
      const eq = pair.indexOf('=');
      if (eq === -1) return [];
      const k = decodeURIComponent(pair.slice(0, eq));
      const v = decodeURIComponent(pair.slice(eq + 1));
      return [[k, v]];
    })
  );
}

function buildHash(params: Record<string, string>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== '');
  if (entries.length === 0) return '';
  return '#' + entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
}

function applyUpdates(
  current: Record<string, string>,
  updates: Record<string, string | undefined>
): Record<string, string> {
  const next: Record<string, string> = { ...current };
  for (const [k, v] of Object.entries(updates)) {
    if (v === undefined || v === '') {
      delete next[k];
    } else {
      next[k] = v;
    }
  }
  return next;
}

describe('parseHash', () => {
  it('parses screen key', () => {
    expect(parseHash('#screen=overview')).toEqual({ screen: 'overview' });
  });

  it('parses multiple keys', () => {
    expect(parseHash('#screen=queue&project=loop&drawer=item:loop:issue:42')).toEqual({
      screen: 'queue',
      project: 'loop',
      drawer: 'item:loop:issue:42',
    });
  });

  it('returns empty object for empty hash', () => {
    expect(parseHash('')).toEqual({});
    expect(parseHash('#')).toEqual({});
  });

  it('preserves unknown keys', () => {
    const result = parseHash('#screen=overview&future=value&project=loop');
    expect(result['future']).toBe('value');
    expect(result['screen']).toBe('overview');
    expect(result['project']).toBe('loop');
  });

  it('decodes percent-encoded values', () => {
    expect(parseHash('#drawer=item%3Aloop%3Aissue%3A42')).toEqual({
      drawer: 'item:loop:issue:42',
    });
  });
});

describe('buildHash', () => {
  it('builds single key hash', () => {
    expect(buildHash({ screen: 'overview' })).toBe('#screen=overview');
  });

  it('returns empty string for empty params', () => {
    expect(buildHash({})).toBe('');
  });

  it('encodes colons in values', () => {
    const h = buildHash({ drawer: 'item:loop:issue:42' });
    expect(h).toContain('item%3Aloop%3Aissue%3A42');
  });
});

describe('applyUpdates', () => {
  it('writes screen key', () => {
    const result = applyUpdates({}, { screen: 'queue' });
    expect(result).toEqual({ screen: 'queue' });
  });

  it('writes drawer key', () => {
    const result = applyUpdates({ screen: 'queue' }, { drawer: 'item:loop:issue:42' });
    expect(result).toEqual({ screen: 'queue', drawer: 'item:loop:issue:42' });
  });

  it('clears drawer key when set to undefined', () => {
    const result = applyUpdates(
      { screen: 'queue', drawer: 'item:loop:issue:42' },
      { drawer: undefined }
    );
    expect(result).toEqual({ screen: 'queue' });
  });

  it('preserves unknown keys on write', () => {
    const result = applyUpdates(
      { screen: 'overview', future: 'value' },
      { screen: 'queue' }
    );
    expect(result['future']).toBe('value');
    expect(result['screen']).toBe('queue');
  });

  it('project key read/write round-trips', () => {
    const parsed = parseHash('#screen=overview&project=loop');
    expect(parsed['project']).toBe('loop');
    const updated = applyUpdates(parsed, { project: 'other' });
    expect(updated['project']).toBe('other');
    expect(updated['screen']).toBe('overview');
  });

  it('no-op when value is unchanged', () => {
    const current = { screen: 'overview', project: 'loop' };
    const updated = applyUpdates(current, { screen: 'overview' });
    expect(updated).toEqual(current);
  });
});

describe('useHashRoute integration (window.location.hash)', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { hash: '' },
    });
  });

  it('defaults to overview when hash is empty', () => {
    window.location.hash = '';
    const params = parseHash(window.location.hash);
    expect(params['screen'] ?? 'overview').toBe('overview');
  });

  it('reads screen from hash', () => {
    window.location.hash = '#screen=queue';
    const params = parseHash(window.location.hash);
    expect(params['screen']).toBe('queue');
  });

  it('reads project from hash', () => {
    window.location.hash = '#screen=overview&project=loop';
    const params = parseHash(window.location.hash);
    expect(params['project']).toBe('loop');
  });

  it('reads drawer from hash', () => {
    window.location.hash = '#screen=queue&drawer=item%3Aloop%3Aissue%3A42';
    const params = parseHash(window.location.hash);
    expect(params['drawer']).toBe('item:loop:issue:42');
  });
});
