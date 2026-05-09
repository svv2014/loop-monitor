import { useState, useEffect } from 'react';

interface TopBarEvent {
  ts: number;
}

interface TopBarProps {
  events: TopBarEvent[];
  online: boolean;
  version: string;
}

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

export default function TopBar({ events, online, version }: TopBarProps) {
  useTick(1000);
  const now = new Date();
  const eventsLastMin = events.filter(e => Date.now() - e.ts < 60_000).length;
  return (
    <div className="topbar">
      <div className="left">
        <span className="mono" style={{ color: 'var(--fg)', fontWeight: 500 }}>
          PIPELINE
          <span style={{ color: 'var(--fg-4)', marginLeft: 6 }}>v{version}</span>
        </span>
        <span style={{ width: 1, height: 14, background: 'var(--border)' }}></span>
        <span><span className="dot"></span> &nbsp;{online ? 'CONNECTED' : 'OFFLINE'}</span>
        <span>: 127.0.0.1:18792</span>
      </div>
      <div className="right">
        <span>{eventsLastMin}/min</span>
        <span>· {events.length.toLocaleString()} events</span>
        <span>· {timeFmt(now)}</span>
      </div>
    </div>
  );
}
