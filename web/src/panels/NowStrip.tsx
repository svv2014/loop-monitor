import type { Worker, FeedItem } from '../lib/types';
import { relTime, durationFmt, useTick } from '../lib/utils';
import EventGlyph from '../components/EventGlyph';

interface NowStripProps {
  workers: Worker[];
  events: FeedItem[];
}

export default function NowStrip({ workers, events }: NowStripProps) {
  useTick(1000);
  const lastEvent = events[0];
  const lastTs = lastEvent ? new Date(lastEvent.created_at).getTime() : 0;

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
              <EventGlyph event={lastEvent.event_type} />
              <span className="mono">{lastEvent.event_type}</span>
              <span className="muted">·</span>
              <span className="muted mono">
                {lastEvent.project}
                {lastEvent.issue_number != null ? `#${lastEvent.issue_number}` : ''}
              </span>
              <span className="muted">·</span>
              <span className="muted">{relTime(lastTs)} ago</span>
            </span>
          )}
        </div>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: workers.length
          ? `repeat(${Math.min(workers.length, 5)}, 1fr)`
          : '1fr',
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
        {workers.map((w, i) => {
          const startedAt = new Date(w.created_at).getTime();
          const name = w.model ?? w.role;
          return (
            <div
              key={i}
              className="worker-beat"
              style={{ '--role-c': `var(--role-${w.role})` } as React.CSSProperties}
            >
              <span className="role-stripe"></span>
              <span className="pulse"></span>
              <div className="meta">
                <div className="agent">
                  <span style={{ color: `var(--role-${w.role})` }}>{w.role}</span>
                  <span style={{ color: 'var(--fg-4)' }}> · </span>
                  <span>{name}</span>
                </div>
                <div className="task">
                  <span className="mono" style={{ color: 'var(--fg-2)' }}>{w.project}</span>
                  <span style={{ color: 'var(--fg-4)' }}> — </span>
                  {w.event_type}
                </div>
              </div>
              <span className="timer">{durationFmt(Date.now() - startedAt)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
