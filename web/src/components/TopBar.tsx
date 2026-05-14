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
  const now = new Date();
  const eventsLastMin = events.filter(e => Date.now() - e.ts < 60_000).length;
  const isFiltered = !!projectFilter;

  const [bannerKey, setBannerKey] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const isStale =
    !!gitSha &&
    !!latestMainSha &&
    gitSha !== 'unknown' &&
    latestMainSha !== 'unknown' &&
    gitSha !== latestMainSha;

  // Reset dismissed state when a new mismatch pair appears
  useEffect(() => {
    if (isStale && gitSha && latestMainSha) {
      const key = `${gitSha}:${latestMainSha}`;
      if (key !== bannerKey) {
        setBannerKey(key);
        setDismissed(false);
      }
    }
  }, [isStale, gitSha, latestMainSha, bannerKey]);

  const showBanner = isStale && !dismissed;

  return (
    <>
      {showBanner && (
        <div
          className="mono"
          style={{
            gridColumn: '1 / -1',
            background: 'color-mix(in srgb, var(--amber, #d97706) 15%, var(--bg-1))',
            borderBottom: '1px solid color-mix(in srgb, var(--amber, #d97706) 40%, transparent)',
            padding: '4px 16px',
            fontSize: 11,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: 'var(--amber, #d97706)',
          }}
        >
          <span>⚠ Update available — running {gitSha}, latest main is {latestMainSha}. Run <code>scripts/redeploy.sh</code> to update.</span>
          <button
            onClick={() => setDismissed(true)}
            style={{
              marginLeft: 'auto',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'inherit',
              fontSize: 13,
              lineHeight: 1,
              padding: '0 4px',
            }}
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      )}
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
    </>
  );
}
