import { useCallback, useEffect, useState } from 'react';

export type Screen = 'overview' | 'queue' | 'projects' | 'workers' | 'project' | 'logs';

export interface HashRoute {
  screen: Screen;
  projectId: string | null;
}

function parseHash(hash: string): HashRoute {
  // Format: #project=<id>
  const m = hash.match(/^#project=(.+)$/);
  if (m) {
    return { screen: 'project', projectId: decodeURIComponent(m[1]) };
  }
  return { screen: 'overview', projectId: null };
}

function buildHash(screen: Screen, projectId: string | null): string {
  if (screen === 'project' && projectId) {
    return `#project=${encodeURIComponent(projectId)}`;
  }
  return '';
}

export function useHashRoute() {
  const [route, setRoute] = useState<HashRoute>(() => parseHash(window.location.hash));

  useEffect(() => {
    const handler = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  const navigateTo = useCallback((screen: Screen, projectId: string | null = null) => {
    const hash = buildHash(screen, projectId);
    history.replaceState(null, '', window.location.pathname + window.location.search + hash);
    setRoute({ screen, projectId });
  }, []);

  return { ...route, navigateTo };
}
