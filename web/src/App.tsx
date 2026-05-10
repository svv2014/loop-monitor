import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Logo from './components/Logo';
import TopBar from './components/TopBar';
import NavRail from './components/NavRail';
import Overview from './screens/Overview';
import { fetchActive, fetchHealth } from './lib/api';

const SCREEN_KEYS: Record<string, string> = {
  '1': 'overview',
  '2': 'queue',
  '3': 'projects',
  '4': 'workers',
};

export default function App() {
  const [screen, setScreen] = useState('overview');

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
      if (next) setScreen(next);
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
      <NavRail screen={screen} setScreen={setScreen} />
      <main className="main">
        {screen === 'overview' && <Overview />}
      </main>
    </div>
  );
}
