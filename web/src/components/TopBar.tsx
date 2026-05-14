import { useState, useEffect } from 'react';

interface TopBarEvent {
  ts: number;
}

interface TopBarProps {
  events: TopBarEvent[];
  online: boolean;
  version: string;
  gitSha?: string;
  latestMainSha?: string;
  allProjectIds: string[];
  projectFilter: string | null;
  onProjectFilterChange: (v: string | null) => void;
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

export default function TopBar({ events, online, version, gitSha, latestMainSha, allProjectIds, projectFilter, onProjectFilterChange }: TopBarProps) {
  useTick(1000);
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const now = new Date();
  const eventsLastMin = events.filter(e => Date.now() - e.ts < 60_000).length;
  const isFiltered = !!projectFilter;

  const shaMismatch =
    gitSha != null &&
    latestMainSha != null &&
    gitSha !== 'unknown' &&
    latestMainSha !== 'unknown' &&
    gitSha !== latestMainSha;

  const showBanner = shaMismatch && !bannerDismissed;

  return (
    <>
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
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <label className="muted mono" style={{ fontSize: 11 }}>Project:</label>
            <select
              className="btn"
              value={projectFilter ?? ''}
              onChange={e => onProjectFilterChange(e.target.value || null)}
              style={{
                cursor: 'pointer',
                border: isFiltered ? '1px solid var(--accent)' : undefined,
                background: isFiltered ? 'color-mix(in srgb, var(--accent) 15%, var(--bg-1))' : undefined,
                color: isFiltered ? 'var(--accent)' : undefined,
              }}
            >
              <option value="">All</option>
              {allProjectIds.map(id => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
          </span>
          <span>{eventsLastMin}/min</span>
          <span>· {events.length.toLocaleString()} events</span>
          <span>· {timeFmt(now)}</span>
        </div>
      </div>
      {showBanner && (
        <div
          className="mono"
          style={{
            gridColumn: '1 / -1',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '6px 16px',
            background: 'color-mix(in srgb, var(--warn) 12%, var(--bg-1))',
            borderBottom: '1px solid color-mix(in srgb, var(--warn) 40%, transparent)',
            fontSize: 12,
            color: 'var(--warn)',
          }}
        >
          <span>
            Service running <strong>{gitSha}</strong> — latest main is <strong>{latestMainSha}</strong>.
            Run <code style={{ background: 'var(--bg-2)', padding: '1px 5px', borderRadius: 3 }}>scripts/redeploy.sh</code> to update.
          </span>
          <button
            onClick={() => setBannerDismissed(true)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--fg-3)',
              cursor: 'pointer',
              fontSize: 14,
              lineHeight: 1,
              padding: '0 4px',
            }}
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}
    </>
  );
}
