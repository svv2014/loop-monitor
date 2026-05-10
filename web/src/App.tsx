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
import { useHashRoute } from './router';
import { fetchActive, fetchHealth } from './lib/api';

const SCREEN_KEYS: Record<string, string> = {
  '1': 'overview',
  '2': 'queue',
  '3': 'projects',
  '4': 'workers',
  '5': 'logs',
};

export default function App() {
  const { screen: hashScreen, projectId: hashProjectId, navigateTo } = useHashRoute();

  // Derive UI screen from hash. 'project' is a sub-state of 'projects' nav item.
  const [navScreen, setNavScreen] = useState<string>(
    hashScreen === 'project' ? 'projects' : hashScreen,
  );
  const [projectId, setProjectId] = useState<string | null>(hashProjectId);
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

  // When the hash changes externally (back/forward), sync local state
  useEffect(() => {
    if (hashScreen === 'project' && hashProjectId) {
      setNavScreen('projects');
      setProjectId(hashProjectId);
    } else if (hashScreen !== 'project') {
      setNavScreen(hashScreen);
    }
  }, [hashScreen, hashProjectId]);

  function handleNavChange(s: string) {
    setNavScreen(s);
    if (s !== 'projects') {
      setProjectId(null);
      navigateTo(s as 'overview' | 'queue' | 'projects' | 'workers' | 'project' | 'logs');
    }
  }

  function handleProjectChange(id: string) {
    setProjectId(id);
    navigateTo('project', id);
  }

  function handleBack() {
    setProjectId(null);
    navigateTo('overview');
    setNavScreen('overview');
  }

  const isProjectDetail = navScreen === 'projects' && projectId != null;

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
        {isProjectDetail && projectId != null ? (
          <ProjectDetail
            projectId={projectId}
            allProjectIds={allProjectIds.length > 0 ? allProjectIds : [projectId]}
            onBack={handleBack}
            onProjectChange={handleProjectChange}
          />
        ) : navScreen === 'overview' ? (
          <Overview />
        ) : navScreen === 'queue' ? (
          <Queue />
        ) : navScreen === 'workers' ? (
          <WorkerDetail />
        ) : navScreen === 'logs' ? (
          <Logs />
        ) : (
          <div style={{ padding: 'var(--pad-4)' }}>
            <p className="muted mono" style={{ fontSize: 12 }}>
              {navScreen === 'projects'
                ? 'Select a project — navigate via URL hash: #project=<id>'
                : `${navScreen} screen coming soon`}
            </p>
            {navScreen === 'projects' && allProjectIds.length > 0 && (
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
