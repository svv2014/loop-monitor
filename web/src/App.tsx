import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Logo from './components/Logo';
import TopBar from './components/TopBar';
import NavRail from './components/NavRail';
import Queue from './screens/Queue';
import { fetchActive, fetchHealth } from './lib/api';
import { useHashRoute } from './router';

const NAV_KEYS: Record<string, string> = {
  '1': 'overview',
  '2': 'queue',
  '3': 'projects',
  '4': 'workers',
};

export default function App() {
  const { screen, setHash } = useHashRoute();

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
    function onKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const id = NAV_KEYS[e.key];
      if (id) setHash({ screen: id });
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [setHash]);

  const events = (activeQuery.data ?? []).map((w) => ({
    ts: new Date(w.created_at).getTime(),
  }));
  const online = !activeQuery.isError;
  const version = healthQuery.data?.monitor_version ?? '…';

  function setScreen(id: string) {
    setHash({ screen: id });
  }

  return (
    <div className="app">
      <Logo />
      <TopBar events={events} online={online} version={version} />
      <NavRail screen={screen} setScreen={setScreen} />
      <main className="main">
        {screen === 'queue' && <Queue />}
      </main>
    </div>
  );
}
