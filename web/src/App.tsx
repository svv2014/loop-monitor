import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Logo from './components/Logo';
import TopBar from './components/TopBar';
import NavRail from './components/NavRail';
import WorkerDetail from './screens/WorkerDetail';
import { fetchActive, fetchHealth } from './lib/api';

type Screen = 'overview' | 'queue' | 'projects' | 'workers';

const KEYMAP: Record<string, Screen> = {
  '1': 'overview',
  '2': 'queue',
  '3': 'projects',
  '4': 'workers',
};

export default function App() {
  const [screen, setScreen] = useState<Screen>('overview');

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const next = KEYMAP[e.key];
      if (next) setScreen(next);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

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

  const events = (activeQuery.data ?? []).map((w) => ({
    ts: new Date(w.created_at).getTime(),
  }));
  const online = !activeQuery.isError;
  const version = healthQuery.data?.monitor_version ?? '…';

  return (
    <div className="app">
      <Logo />
      <TopBar events={events} online={online} version={version} />
      <NavRail screen={screen} setScreen={s => setScreen(s as Screen)} />
      <main className="main">
        {screen === 'workers' && (
          <WorkerDetail setScreen={s => setScreen(s as Screen)} />
        )}
      </main>
    </div>
  );
}
