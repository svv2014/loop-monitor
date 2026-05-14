import { useCallback, useEffect, useState } from 'react';

export type Screen = 'overview' | 'queue' | 'projects' | 'workers' | 'project' | 'logs' | 'analytics' | 'timeline';

export interface HashRoute {
  screen: Screen;
  projectId: string | null;
  drawer: string | null;
}

function parseHash(hash: string): { known: HashRoute; unknown: Record<string, string> } {
  const unknown: Record<string, string> = {};

  if (!hash || hash === '#') {
    return {
      known: { screen: 'overview', projectId: null, drawer: null },
      unknown,
    };
  }

  // Strip leading '#'
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;

  // Legacy single-key format: #project=<id>  (no & separator)
  // We also handle the new multi-key format: screen=x&project=y&drawer=z
  const params = new URLSearchParams(raw);

  let screen: Screen = 'overview';
  let projectId: string | null = null;
  let drawer: string | null = null;

  for (const [key, value] of params.entries()) {
    if (key === 'screen') {
      screen = value as Screen;
    } else if (key === 'project') {
      projectId = value;
      // Legacy: if only 'project' is present and no 'screen', infer screen='project'
      if (!params.has('screen')) {
        screen = 'project';
      }
    } else if (key === 'drawer') {
      drawer = value;
    } else {
      unknown[key] = value;
    }
  }

  return { known: { screen, projectId, drawer }, unknown };
}

function buildHash(
  screen: Screen,
  projectId: string | null,
  drawer: string | null,
  unknown: Record<string, string>,
): string {
  const params = new URLSearchParams();

  // Write screen (omit if it's 'overview' AND everything else is empty — keep URLs clean)
  const hasOtherKeys = projectId || drawer || Object.keys(unknown).length > 0;
  if (screen !== 'overview' || hasOtherKeys) {
    params.set('screen', screen);
  }

  if (projectId) {
    params.set('project', projectId);
  }

  if (drawer) {
    params.set('drawer', drawer);
  }

  for (const [key, value] of Object.entries(unknown)) {
    params.set(key, value);
  }

  const str = params.toString();
  return str ? `#${str}` : '';
}

export function useHashRoute() {
  const [parsed, setParsed] = useState(() => parseHash(window.location.hash));

  useEffect(() => {
    const handler = () => setParsed(parseHash(window.location.hash));
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  const { known: route, unknown } = parsed;

  const navigateTo = useCallback(
    (
      screen: Screen,
      projectId: string | null = null,
      opts?: { drawer?: string | null; pushState?: boolean },
    ) => {
      const drawer = opts?.drawer !== undefined ? opts.drawer : route.drawer;
      const hash = buildHash(screen, projectId, drawer ?? null, unknown);
      if (opts?.pushState) {
        history.pushState(null, '', window.location.pathname + window.location.search + hash);
      } else {
        history.replaceState(null, '', window.location.pathname + window.location.search + hash);
      }
      setParsed(prev => ({
        known: { screen, projectId, drawer: drawer ?? null },
        unknown: prev.unknown,
      }));
    },
    [route.drawer, unknown],
  );

  const setDrawer = useCallback(
    (drawer: string | null) => {
      const hash = buildHash(route.screen, route.projectId, drawer, unknown);
      history.replaceState(null, '', window.location.pathname + window.location.search + hash);
      setParsed(prev => ({
        known: { ...prev.known, drawer },
        unknown: prev.unknown,
      }));
    },
    [route.screen, route.projectId, unknown],
  );

  const setProjectFilter = useCallback(
    (filter: string | null) => {
      const newUnknown = { ...unknown };
      if (filter) {
        newUnknown['project_filter'] = filter;
      } else {
        delete newUnknown['project_filter'];
      }
      const hash = buildHash(route.screen, route.projectId, route.drawer, newUnknown);
      history.replaceState(null, '', window.location.pathname + window.location.search + hash);
      setParsed(prev => ({
        known: prev.known,
        unknown: newUnknown,
      }));
    },
    [route.screen, route.projectId, route.drawer, unknown],
  );

  const navigateToTimeline = useCallback(
    (slug: string, num: number) => {
      const newUnknown = { ...unknown, issue_num: String(num) };
      const hash = buildHash('timeline', slug, null, newUnknown);
      history.pushState(null, '', window.location.pathname + window.location.search + hash);
      setParsed({ known: { screen: 'timeline', projectId: slug, drawer: null }, unknown: newUnknown });
    },
    [unknown],
  );

  const rawIssueNum = unknown['issue_num'];
  const issueNum = rawIssueNum != null ? parseInt(rawIssueNum, 10) : null;

  return {
    screen: route.screen,
    projectId: route.projectId,
    drawer: route.drawer,
    projectFilter: unknown['project_filter'] ?? null,
    issueNum: Number.isNaN(issueNum) ? null : issueNum,
    navigateTo,
    setDrawer,
    setProjectFilter,
    navigateToTimeline,
  };
}
