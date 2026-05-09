import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Logo from './components/Logo';
import TopBar from './components/TopBar';
import NavRail from './components/NavRail';
import { fetchActive, fetchHealth } from './lib/api';

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
      <main className="main"></main>
    </div>
  );
}
