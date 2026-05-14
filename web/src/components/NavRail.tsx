import type { ReactNode } from 'react';

interface NavRailProps {
  screen: string;
  setScreen: (screen: string) => void;
}

const NAV_ICONS: Record<string, ReactNode> = {
  overview: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
      <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
    </svg>
  ),
  queue: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3 6h18M3 12h12M3 18h6"/>
    </svg>
  ),
  projects: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 12l9 4 9-4"/><path d="M3 17l9 4 9-4"/>
    </svg>
  ),
  workers: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/>
      <circle cx="17" cy="9" r="2.5"/><path d="M14 18c0-2.5 1.6-4 3-4s3 1.5 3 4"/>
    </svg>
  ),
  logs: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="4" y="3" width="16" height="18" rx="1"/>
      <path d="M8 8h8M8 12h8M8 16h5"/>
    </svg>
  ),
  cost: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="14" width="4" height="7"/><rect x="10" y="9" width="4" height="12"/>
      <rect x="17" y="4" width="4" height="17"/>
    </svg>
  ),
  analytics: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="9"/><path d="M12 3v9l5 5"/>
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="3"/>
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>
    </svg>
  ),
};

export default function NavRail({ screen, setScreen }: NavRailProps) {
  const items = [
    { id: 'overview', label: 'Overview' },
    { id: 'queue',    label: 'Action Queue' },
    { id: 'projects', label: 'Projects' },
    { id: 'workers',  label: 'Workers' },
    { id: 'logs',     label: 'Logs' },
    { id: 'cost',      label: 'Cost' },
    { id: 'analytics', label: 'Analytics' },
  ];
  return (
    <div className="nav">
      {items.map(it => (
        <button key={it.id}
          className={`nav-item ${screen === it.id ? 'active' : ''}`}
          onClick={() => setScreen(it.id)}>
          {NAV_ICONS[it.id]}
          <span className="nav-tip">{it.label}</span>
        </button>
      ))}
      <div style={{ flex: 1 }}></div>
      <button className="nav-item" title="Settings">
        {NAV_ICONS.settings}
        <span className="nav-tip">Settings</span>
      </button>
    </div>
  );
}
