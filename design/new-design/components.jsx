/* global React */
const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ----- Time helpers -----
function relTime(ts) {
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return s + 's';
  if (s < 3600) return Math.floor(s / 60) + 'm';
  if (s < 86400) return Math.floor(s / 3600) + 'h';
  return Math.floor(s / 86400) + 'd';
}
function durationFmt(ms) {
  const s = Math.floor(ms / 1000);
  if (s < 60) return s + 's';
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m < 60) return `${m}m ${String(r).padStart(2, '0')}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}
function timeFmt(ts) {
  const d = new Date(ts);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

// ----- Live clock hook -----
function useTick(ms = 1000) {
  const [, setN] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setN(n => n + 1), ms);
    return () => clearInterval(id);
  }, [ms]);
}

// ----- Brand glyph -----
function Logo() {
  return (
    <div className="logo">
      <div className="glyph"></div>
    </div>
  );
}

// ----- Top bar -----
function TopBar({ events, online, version }) {
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

// ----- Left nav -----
const NAV_ICONS = {
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
  settings: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="3"/>
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>
    </svg>
  ),
};

function NavRail({ screen, setScreen }) {
  const items = [
    { id: 'overview', label: 'Overview' },
    { id: 'queue',    label: 'Action Queue' },
    { id: 'projects', label: 'Projects' },
    { id: 'workers',  label: 'Workers' },
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

// ----- Role tag -----
function RoleTag({ role, solid }) {
  return (
    <span className={`tag role-${role}`} style={solid ? {
      background: `var(--role-${role})`,
      color: 'var(--bg)',
      borderColor: `var(--role-${role})`,
    } : {}}>
      {role}
    </span>
  );
}

// ----- Event glyph -----
function EventGlyph({ event }) {
  const map = {
    po_start:    { sym: '▸', cls: 'role-po' },
    po_done:     { sym: '◆', cls: 'role-po' },
    dev_start:   { sym: '▸', cls: 'role-dev' },
    dev_done:    { sym: '◆', cls: 'role-dev' },
    qa_pass:     { sym: '✓', cls: 'role-qa' },
    qa_fail:     { sym: '✗', cls: 'role-qa', color: 'var(--fail)' },
    review_done: { sym: '◆', cls: 'role-reviewer' },
    merge_done:  { sym: '⬢', cls: 'role-merge' },
    judge_done:  { sym: '★', cls: 'role-judge' },
  };
  const m = map[event] || { sym: '·', cls: 'muted' };
  return (
    <span className={m.cls} style={{
      fontFamily: 'var(--font-mono)',
      fontSize: 13,
      lineHeight: 1,
      ...(m.color ? { color: m.color } : {}),
    }}>{m.sym}</span>
  );
}

window.PMComponents = {
  relTime, durationFmt, timeFmt, useTick,
  Logo, TopBar, NavRail, RoleTag, EventGlyph,
};
