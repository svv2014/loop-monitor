import { useCallback, useEffect, useState } from 'react';

export type Screen = 'overview' | 'queue' | 'projects' | 'workers' | 'project' | 'logs' | 'timeline';

export interface HashRoute {
  screen: Screen;
  projectId: string | null;
  issueNum: number | null;
}

function parseHash(hash: string): HashRoute {
  // #timeline=<slug>&num=<N>
  const tm = hash.match(/^#timeline=([^&]+)&num=(\d+)$/);
  if (tm) {
    return { screen: 'timeline', projectId: decodeURIComponent(tm[1]), issueNum: parseInt(tm[2], 10) };
  }
  // #project=<id>
  const m = hash.match(/^#project=(.+)$/);
  if (m) {
    return { screen: 'project', projectId: decodeURIComponent(m[1]), issueNum: null };
  }
  return { screen: 'overview', projectId: null, issueNum: null };
}

function buildHash(screen: Screen, projectId: string | null, issueNum: number | null = null): string {
  if (screen === 'timeline' && projectId && issueNum != null) {
    return `#timeline=${encodeURIComponent(projectId)}&num=${issueNum}`;
  }
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

  const navigateTo = useCallback((screen: Screen, projectId: string | null = null, issueNum: number | null = null) => {
    const hash = buildHash(screen, projectId, issueNum);
    history.replaceState(null, '', window.location.pathname + window.location.search + hash);
    setRoute({ screen, projectId, issueNum });
  }, []);

  return { ...route, navigateTo };
}
