import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Logo from './components/Logo';
import NavRail from './components/NavRail';
import TopBar from './components/TopBar';
import Overview from './screens/Overview';
import Logs from './screens/Logs';
import ProjectDetail from './screens/ProjectDetail';
import Queue from './screens/Queue';
import WorkerDetail from './screens/WorkerDetail';
import Cost from './screens/Cost';
import Analytics from './screens/Analytics';
import { useHashRoute } from './router';
import { fetchActive, fetchHealth } from './lib/api';

const SCREEN_KEYS: Record<string, string> = {
  '1': 'overview',
  '2': 'queue',
  '3': 'projects',
  '4': 'workers',
  '5': 'logs',
  '6': 'cost',
  '7': 'analytics',
};

export default function App() {
  const { screen: hashScreen, projectId: hashProjectId, navigateTo } = useHashRoute();

  // 'cost' and 'analytics' are local-only — not stored in the hash — so we track them separately.
  const [showCost, setShowCost] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);

  // Derive nav screen from hash. 'project' is a sub-state of 'projects' nav item.
  const hashNavScreen = hashScreen === 'project' ? 'projects' : hashScreen;
  // When cost or analytics is active, override; otherwise use hash-derived value.
  const navScreen = showCost ? 'cost' : showAnalytics ? 'analytics' : hashNavScreen;
  const projectId = hashProjectId;

  const [allProjectIds, setAllProjectIds] = useState<string[]>([]);

  // Fetch all known project IDs from /api/status for the project switcher
  useEffect(() => {
    fetch('/api/status')
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: Array<{ project: string }>) => {
        const ids = Array.from(new Set(data.map(e => e.project))).sort();
        setAllProjectIds(ids);
      })
      .catch(() => undefined);
  }, []);

  // When hash changes externally (back/forward), clear overlays
  useEffect(() => {
    setShowCost(false);
    setShowAnalytics(false);
  }, [hashScreen]);

  function handleNavChange(s: string) {
    if (s === 'cost') {
      setShowCost(true);
      setShowAnalytics(false);
    } else if (s === 'analytics') {
      setShowAnalytics(true);
      setShowCost(false);
    } else {
      setShowCost(false);
      setShowAnalytics(false);
      navigateTo(s as 'overview' | 'queue' | 'projects' | 'workers' | 'project' | 'logs', null, {
        drawer: null,
        pushState: true,
      });
    }
  }

  function handleProjectChange(id: string) {
    setShowCost(false);
    navigateTo('project', id, { drawer: null, pushState: true });
  }

  function handleBack() {
    setShowCost(false);
    navigateTo('overview', null, { pushState: true });
  }

  const isProjectDetail = hashNavScreen === 'projects' && projectId != null;

  const activeQuery = useQuery({
    queryKey: ['active'],
    queryFn: () => fetchActive(),
    refetchInterval: 5000,
    staleTime: 0,
  });

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: () => fetchHealth(),
    staleTime: 60_000,
  });

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const next = SCREEN_KEYS[e.key];
      if (next) handleNavChange(next);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const events = (activeQuery.data ?? []).map((w) => ({
    ts: new Date(w.created_at).getTime(),
  }));
  const online = !activeQuery.isError;
  const version = healthQuery.data?.monitor_version ?? '…';

  return (
    <div className="app">
      <Logo />
      <TopBar events={events} online={online} version={version} />
      <NavRail screen={isProjectDetail ? 'projects' : navScreen} setScreen={handleNavChange} />
      <main className="main">
        {showCost ? (
          <Cost />
        ) : (showAnalytics || hashNavScreen === 'analytics') ? (
          <Analytics />
        ) : isProjectDetail && projectId != null ? (
          <ProjectDetail
            projectId={projectId}
            allProjectIds={allProjectIds.length > 0 ? allProjectIds : [projectId]}
            onBack={handleBack}
            onProjectChange={handleProjectChange}
          />
        ) : hashNavScreen === 'overview' ? (
          <Overview />
        ) : hashNavScreen === 'queue' ? (
          <Queue />
        ) : hashNavScreen === 'workers' ? (
          <WorkerDetail />
        ) : hashNavScreen === 'logs' ? (
          <Logs />
        ) : (
          <div style={{ padding: 'var(--pad-4)' }}>
            <p className="muted mono" style={{ fontSize: 12 }}>
              {hashNavScreen === 'projects'
                ? 'Select a project — navigate via URL hash: #screen=project&project=<id>'
                : `${hashNavScreen} screen coming soon`}
            </p>
            {hashNavScreen === 'projects' && allProjectIds.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--pad-2)', marginTop: 'var(--pad-3)' }}>
                {allProjectIds.map(id => (
                  <button key={id} className="btn" onClick={() => handleProjectChange(id)}>{id}</button>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
