import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchActive } from '../lib/api';

function timeFmt(d: Date): string {
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

function useTick(ms = 1000) {
  const [, setN] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setN(n => n + 1), ms);
    return () => clearInterval(id);
  }, [ms]);
}

export function TopBar() {
  useTick(1000);
  const now = new Date();
  const { data: workers, isError } = useQuery({
    queryKey: ['active'],
    queryFn: () => fetchActive(),
    refetchInterval: 5000,
    staleTime: 0,
  });
  const online = !isError;
  return (
    <div className="topbar">
      <div className="left">
        <span className="mono" style={{ color: 'var(--fg)', fontWeight: 500 }}>
          PIPELINE
          <span style={{ color: 'var(--fg-4)', marginLeft: 6 }}>v2</span>
        </span>
        <span style={{ width: 1, height: 14, background: 'var(--border)' }}></span>
        <span><span className="dot"></span>&nbsp;{online ? 'CONNECTED' : 'OFFLINE'}</span>
        <span>· {workers?.length ?? 0} active</span>
      </div>
      <div className="right">
        <span>{timeFmt(now)}</span>
      </div>
    </div>
  );
}
