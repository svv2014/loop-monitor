import { useCallback, useEffect, useState } from 'react';

type HashParams = Record<string, string | undefined>;

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

export function useHashRoute() {
  const [params, setParams] = useState<Record<string, string>>(() =>
    parseHash(window.location.hash)
  );

  useEffect(() => {
    function onHashChange() {
      setParams(parseHash(window.location.hash));
    }
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const setHash = useCallback((updates: HashParams) => {
    const current = parseHash(window.location.hash);
    const next: Record<string, string> = { ...current };
    for (const [k, v] of Object.entries(updates)) {
      if (v === undefined || v === '') {
        delete next[k];
      } else {
        next[k] = v;
      }
    }
    const newHash = buildHash(next);
    if (newHash !== window.location.hash && !(newHash === '' && window.location.hash === '')) {
      window.location.hash = newHash || '#';
    }
  }, []);

  const screen = params['screen'] ?? 'overview';
  const project = params['project'] ?? '';
  const drawer = params['drawer'] ?? '';

  return { params, screen, project, drawer, setHash };
}
