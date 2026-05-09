import { useCallback, useEffect, useState } from 'react';

export type Screen = 'overview' | 'project';

export interface HashRoute {
  screen: Screen;
  projectId: string | null;
}

function parseHash(hash: string): HashRoute {
  // Format: #project=<id>
  const match = hash.match(/^#project=(.+)$/);
  if (match) {
    return { screen: 'project', projectId: decodeURIComponent(match[1]) };
  }
  return { screen: 'overview', projectId: null };
}

function buildHash(screen: Screen, projectId: string | null): string {
  if (screen === 'project' && projectId) {
    return `#project=${encodeURIComponent(projectId)}`;
  }
  return '';
}

export function useHashRoute(): HashRoute & {
  navigateTo: (screen: Screen, projectId?: string | null) => void;
} {
  const [route, setRoute] = useState<HashRoute>(() => parseHash(window.location.hash));

  useEffect(() => {
    const handler = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  const navigateTo = useCallback((screen: Screen, projectId?: string | null) => {
    const id = projectId ?? null;
    const hash = buildHash(screen, id);
    history.replaceState(null, '', window.location.pathname + window.location.search + hash);
    setRoute({ screen, projectId: id });
  }, []);

  return { ...route, navigateTo };
}
