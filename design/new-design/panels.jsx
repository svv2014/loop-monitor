/* global React, PipelineData, PMComponents */
const { useState, useEffect, useRef, useMemo } = React;
const { relTime, durationFmt, timeFmt, useTick, RoleTag, EventGlyph } = PMComponents;

// ====== NOW STRIP — currently-active workers (HERO) ======
function NowStrip({ workers, events }) {
  useTick(1000);
  const lastEvent = events[0];
  return (
    <div className="now-strip">
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 20px 6px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="dot"></span>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            textTransform: 'uppercase',
            letterSpacing: '0.12em',
            color: 'var(--fg)',
          }}>LIVE — {workers.length} worker{workers.length !== 1 ? 's' : ''} running</span>
        </div>
        <div className="ticker" style={{ maxWidth: '50%' }}>
          {lastEvent && (
            <span className="item">
              <EventGlyph event={lastEvent.event}/>
              <span className="mono">{lastEvent.event}</span>
              <span className="muted">·</span>
              <span className="muted mono">{lastEvent.project}#{lastEvent.issue_num}</span>
              <span className="muted">·</span>
              <span className="muted">{relTime(lastEvent.ts)} ago</span>
            </span>
          )}
        </div>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: workers.length ? `repeat(${Math.min(workers.length, 5)}, 1fr)` : '1fr',
      }}>
        {workers.length === 0 && (
          <div style={{
            padding: '24px 20px',
            color: 'var(--fg-3)',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            textAlign: 'center',
          }}>
            pipeline is idle — no active workers
          </div>
        )}
        {workers.map(w => (
          <div key={w.id} className="worker-beat" style={{ '--role-c': `var(--role-${w.role})` }}>
            <span className="role-stripe"></span>
            <span className="pulse"></span>
            <div className="meta">
              <div className="agent">
                <span style={{ color: `var(--role-${w.role})` }}>{w.role}</span>
                <span style={{ color: 'var(--fg-4)' }}> · </span>
                <span>{w.name}</span>
              </div>
              <div className="task">
                <span className="mono" style={{ color: 'var(--fg-2)' }}>{w.project}</span>
                <span style={{ color: 'var(--fg-4)' }}> — </span>
                {w.task}
              </div>
            </div>
            <span className="timer">{durationFmt(Date.now() - w.startedAt)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ====== 24h ACTIVITY BARS ======
function Activity24h({ buckets }) {
  const max = Math.max(1, ...buckets.map(b => b.total));
  const ROLE_ORDER = ['po', 'dev', 'qa', 'reviewer', 'merge', 'judge'];
  return (
    <div className="panel">
      <div className="panel-h">
        <span>24h pipeline activity</span>
        <span className="muted">
          {ROLE_ORDER.map(r => (
            <span key={r} style={{ marginLeft: 12 }}>
              <span style={{
                display: 'inline-block',
                width: 8, height: 8, marginRight: 4, verticalAlign: 'middle',
                background: `var(--role-${r})`,
              }}></span>{r}
            </span>
          ))}
        </span>
      </div>
      <div style={{ position: 'relative', height: 130, padding: '14px 0 24px' }}>
        <div className="bars">
          {buckets.map((b, i) => (
            <div key={i} className="bar-col">
              {ROLE_ORDER.map(r => {
                const v = b.counts[r] || 0;
                if (!v) return null;
                return <div key={r} className="bar-seg" style={{
                  background: `var(--role-${r})`,
                  height: `${(v / max) * 100}%`,
                }}/>;
              })}
              {(i % 6 === 0) && <div className="bar-tick">{String(b.hour).padStart(2, '0')}:00</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ====== PROJECT CARD ======
function ProjectCard({ p, onClick }) {
  const isBusy = p.status === 'busy';
  return (
    <div className={`proj-card ${isBusy ? 'busy' : ''}`} onClick={onClick}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className={`status-dot ${isBusy ? 'busy' : 'idle'}`}></span>
          <span style={{ fontWeight: 500, fontSize: 13 }}>{p.id}</span>
        </div>
        <span className="tag" style={{ color: isBusy ? 'var(--accent)' : 'var(--fg-4)' }}>
          {isBusy ? 'BUSY' : 'IDLE'}
        </span>
      </div>
      {isBusy && p.busyWorker ? (
        <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
          <RoleTag role={p.busyWorker.role}/>
          <span className="mono" style={{ marginLeft: 6 }}>{p.busyWorker.name}</span>
        </div>
      ) : (
        <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
          last: <span className="mono">{p.lastEvent || '—'}</span> · {p.lastTs ? relTime(p.lastTs) + ' ago' : '—'}
        </div>
      )}
      <div style={{
        display: 'flex',
        alignItems: 'baseline',
        justifyContent: 'space-between',
        paddingTop: 8,
        borderTop: '1px solid var(--border)',
      }}>
        <span className="num" style={{ fontSize: 20, color: 'var(--fg)' }}>{p.points}</span>
        <span className="muted mono" style={{ fontSize: 10 }}>{p.totalEvents} ev / 24h</span>
      </div>
    </div>
  );
}

// ====== LEADERBOARD ======
function Leaderboard({ events }) {
  const [by, setBy] = useState('role');
  const rows = useMemo(() => PipelineData.buildLeaderboard(events, by).slice(0, 8), [events, by]);
  const max = Math.max(1, ...rows.map(r => r.points));
  return (
    <div className="panel">
      <div className="panel-h">
        <span>Leaderboard</span>
        <span className="actions">
          <button className={`btn ${by === 'role' ? 'primary' : ''}`} onClick={() => setBy('role')}>by role</button>
          <button className={`btn ${by === 'agent' ? 'primary' : ''}`} onClick={() => setBy('agent')}>by agent</button>
        </span>
      </div>
      <table className="t">
        <thead>
          <tr>
            <th style={{ width: 30 }}>#</th>
            <th>{by === 'role' ? 'Role' : 'Agent'}</th>
            <th style={{ textAlign: 'right' }}>Verdicts</th>
            <th style={{ textAlign: 'right' }}>Points</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.key}>
              <td className="muted mono">{String(i + 1).padStart(2, '0')}</td>
              <td>
                {by === 'role'
                  ? <RoleTag role={r.key}/>
                  : <span className="mono" style={{ fontSize: 12 }}>{r.key}</span>}
              </td>
              <td className="num muted" style={{ textAlign: 'right' }}>{r.verdicts}</td>
              <td style={{ textAlign: 'right', position: 'relative' }}>
                <div style={{
                  position: 'absolute', right: 0, top: 0, bottom: 0,
                  width: `${(r.points / max) * 100}%`,
                  background: 'oklch(0.82 0.18 145 / 0.08)',
                  pointerEvents: 'none',
                }}/>
                <span className="num" style={{ position: 'relative', color: 'var(--fg)' }}>{r.points}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ====== ACTIVITY FEED ======
function ActivityFeed({ events, onSelectProject }) {
  const [filter, setFilter] = useState('all');
  const rows = useMemo(() => {
    let r = events;
    if (filter !== 'all') r = r.filter(e => e.role === filter);
    return r.slice(0, 60);
  }, [events, filter]);
  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="panel-h">
        <span>Activity feed</span>
        <span className="actions">
          {['all', 'po', 'dev', 'qa', 'reviewer', 'merge', 'judge'].map(r => (
            <button key={r}
              className={`btn ${filter === r ? 'primary' : ''}`}
              onClick={() => setFilter(r)}>{r}</button>
          ))}
        </span>
      </div>
      <div style={{ overflow: 'auto', maxHeight: 480 }}>
        {rows.map((e, i) => (
          <div key={e.id} className={`feed-row ${i === 0 && e._fresh ? 'fresh' : ''}`}>
            <EventGlyph event={e.event}/>
            <div style={{ minWidth: 0 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <RoleTag role={e.role}/>
                <span className="mono" style={{ fontSize: 12 }}>{e.event}</span>
                <span className="muted mono" style={{ fontSize: 11 }}>
                  · {e.project}#{e.issue_num}
                </span>
              </div>
              <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                <span className="mono">{e.agent}/{e.model}</span>
                {e.duration_ms ? <span> · {durationFmt(e.duration_ms)}</span> : null}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              {e.points > 0 && <div className="mono" style={{ color: 'var(--accent)', fontSize: 12 }}>+{e.points} pts</div>}
              <div className="muted mono" style={{ fontSize: 10 }}>{relTime(e.ts)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

window.PMPanels = {
  NowStrip, Activity24h, ProjectCard, Leaderboard, ActivityFeed,
};
