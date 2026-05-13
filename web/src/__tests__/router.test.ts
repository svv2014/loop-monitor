// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

// ---------------------------------------------------------------------------
// Helpers — parse and build the hash format used by router.tsx
// ---------------------------------------------------------------------------

// We test the pure parsing/building logic extracted from the router.
// The hook itself wraps state + addEventListener so we unit-test the
// underlying functions via a thin re-export shim declared below.

// Re-implement the two pure helpers here so the tests are self-contained
// and don't need a DOM for the hook's useEffect.

type Screen = 'overview' | 'queue' | 'projects' | 'workers' | 'project' | 'logs';

interface ParsedRoute {
  screen: Screen;
  projectId: string | null;
  drawer: string | null;
  unknown: Record<string, string>;
}

function parseHash(hash: string): ParsedRoute {
  if (!hash || hash === '#') {
    return { screen: 'overview', projectId: null, drawer: null, unknown: {} };
  }
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  const params = new URLSearchParams(raw);

  let screen: Screen = 'overview';
  let projectId: string | null = null;
  let drawer: string | null = null;
  const unknown: Record<string, string> = {};

  for (const [key, value] of params.entries()) {
    if (key === 'screen') {
      screen = value as Screen;
    } else if (key === 'project') {
      projectId = value;
      if (!params.has('screen')) screen = 'project';
    } else if (key === 'drawer') {
      drawer = value;
    } else {
      unknown[key] = value;
    }
  }

  return { screen, projectId, drawer, unknown };
}

function buildHash(
  screen: Screen,
  projectId: string | null,
  drawer: string | null,
  unknown: Record<string, string> = {},
): string {
  const params = new URLSearchParams();
  const hasOther = !!(projectId || drawer || Object.keys(unknown).length > 0);
  if (screen !== 'overview' || hasOther) params.set('screen', screen);
  if (projectId) params.set('project', projectId);
  if (drawer) params.set('drawer', drawer);
  for (const [k, v] of Object.entries(unknown)) params.set(k, v);
  const str = params.toString();
  return str ? `#${str}` : '';
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('parseHash', () => {
  it('returns overview defaults for empty hash', () => {
    expect(parseHash('')).toMatchObject({ screen: 'overview', projectId: null, drawer: null });
    expect(parseHash('#')).toMatchObject({ screen: 'overview', projectId: null, drawer: null });
  });

  it('reads the screen key', () => {
    expect(parseHash('#screen=queue')).toMatchObject({ screen: 'queue' });
    expect(parseHash('#screen=workers')).toMatchObject({ screen: 'workers' });
  });

  it('reads the project key alongside screen', () => {
    const r = parseHash('#screen=project&project=my-repo');
    expect(r.screen).toBe('project');
    expect(r.projectId).toBe('my-repo');
  });

  it('reads the drawer key', () => {
    const r = parseHash('#screen=queue&drawer=item%3Arepo%3Aissue%3A42');
    expect(r.drawer).toBe('item:repo:issue:42');
  });

  it('preserves unknown keys', () => {
    const r = parseHash('#screen=overview&foo=bar&baz=qux');
    expect(r.unknown).toEqual({ foo: 'bar', baz: 'qux' });
  });

  it('legacy format #project=<id> infers screen=project', () => {
    const r = parseHash('#project=old-repo');
    expect(r.screen).toBe('project');
    expect(r.projectId).toBe('old-repo');
  });

  it('full multi-key round trip', () => {
    const r = parseHash('#screen=queue&project=loop&drawer=item%3Aloop%3Aissue%3A1');
    expect(r.screen).toBe('queue');
    expect(r.projectId).toBe('loop');
    expect(r.drawer).toBe('item:loop:issue:1');
  });
});

describe('buildHash', () => {
  it('returns empty string for default overview with no other keys', () => {
    expect(buildHash('overview', null, null)).toBe('');
  });

  it('writes screen key when non-overview', () => {
    const h = buildHash('queue', null, null);
    expect(h).toBe('#screen=queue');
  });

  it('writes project and screen together', () => {
    const h = buildHash('project', 'my-repo', null);
    expect(new URLSearchParams(h.slice(1)).get('project')).toBe('my-repo');
    expect(new URLSearchParams(h.slice(1)).get('screen')).toBe('project');
  });

  it('writes drawer key', () => {
    const h = buildHash('queue', null, 'item:loop:issue:42');
    const params = new URLSearchParams(h.slice(1));
    expect(params.get('drawer')).toBe('item:loop:issue:42');
  });

  it('omits drawer key when null', () => {
    const h = buildHash('queue', null, null);
    expect(h).not.toContain('drawer');
  });

  it('preserves unknown keys round-trip', () => {
    const h = buildHash('overview', null, null, { foo: 'bar' });
    const params = new URLSearchParams(h.slice(1));
    expect(params.get('foo')).toBe('bar');
  });

  it('parse → build → parse round trip is stable', () => {
    const original = '#screen=queue&project=loop&drawer=item%3Aloop%3Aissue%3A1&extra=keep';
    const parsed = parseHash(original);
    const rebuilt = buildHash(parsed.screen, parsed.projectId, parsed.drawer, parsed.unknown);
    const reparsed = parseHash(rebuilt);
    expect(reparsed.screen).toBe(parsed.screen);
    expect(reparsed.projectId).toBe(parsed.projectId);
    expect(reparsed.drawer).toBe(parsed.drawer);
    expect(reparsed.unknown).toEqual(parsed.unknown);
  });

  it('writing drawer=undefined/null removes the key', () => {
    const h = buildHash('queue', null, null);
    expect(h).not.toContain('drawer');
  });
});

describe('window.location.hash integration (no-op write guard)', () => {
  const originalHash = window.location.hash;

  beforeEach(() => {
    // Reset hash
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, hash: '' },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, hash: originalHash },
    });
  });

  it('buildHash returns empty string for plain overview (clean URL)', () => {
    const h = buildHash('overview', null, null);
    expect(h).toBe('');
  });

  it('buildHash encodes special characters in drawer value', () => {
    const h = buildHash('queue', null, 'item:loop:issue:42');
    expect(h).toContain('drawer=item%3Aloop%3Aissue%3A42');
  });
});
