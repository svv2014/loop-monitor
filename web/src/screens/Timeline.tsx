import { useEffect, useState } from 'react';

interface TimelineEvent {
  id: number;
  project: string;
  role: string | null;
  model: string | null;
  event_type: string;
  issue_number: number | null;
  pr_number: number | null;
  detail: string | null;
  payload: Record<string, unknown> | null;
  loop_id: string | null;
  created_at: string;
}

interface TimelineResponse {
  events: TimelineEvent[];
}

interface TimelineProps {
  slug: string;
  num: number;
  onBack: () => void;
}

const BADGE_STYLES: Record<string, { color: string; bg: string }> = {
  label_change:     { color: '#a78bfa', bg: 'rgba(167,139,250,0.12)' },
  reconcile:        { color: '#34d399', bg: 'rgba(52,211,153,0.12)' },
  reconcile_check:  { color: '#6ee7b7', bg: 'rgba(110,231,183,0.10)' },
  handler:          { color: '#60a5fa', bg: 'rgba(96,165,250,0.12)' },
  merge:            { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
};

const NEUTRAL_BADGE = { color: 'var(--fg-3)', bg: 'var(--bg-2)' };

function badgeStyle(eventType: string): { color: string; bg: string } {
  for (const prefix of Object.keys(BADGE_STYLES)) {
    if (eventType === prefix || eventType.startsWith(prefix + '_') || eventType.startsWith(prefix + ':')) {
      return BADGE_STYLES[prefix];
    }
  }
  return NEUTRAL_BADGE;
}

function fmtTs(isoStr: string): string {
  try {
    const d = new Date(isoStr.includes('T') ? isoStr : isoStr + 'Z');
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return isoStr;
  }
}

export default function Timeline({ slug, num, onBack }: TimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [showSkipped, setShowSkipped] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    const skipParam = showSkipped ? 'false' : 'true';
    fetch(`/api/timeline?slug=${encodeURIComponent(slug)}&num=${num}&skip_reconcile_skip=${skipParam}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: TimelineResponse) => {
        setEvents(data.events);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, [slug, num, showSkipped]);

  return (
    <div data-testid="timeline">
      {/* Header */}
      <div className="screen-h" style={{ display: 'flex', alignItems: 'center', gap: 'var(--pad-3)', padding: 'var(--pad-2) var(--pad-4)' }}>
        <button className="btn" onClick={onBack}>← Back</button>
        <h1 style={{ flex: 1, margin: 0, fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500, letterSpacing: '0.04em' }}>
          <span className="muted">timeline /</span> {slug} <span className="muted">·</span> #{num}
        </h1>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-3)', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showSkipped}
            onChange={e => setShowSkipped(e.target.checked)}
          />
          Show reconcile skips
        </label>
      </div>

      {/* Body */}
      <div style={{ padding: 'var(--pad-4)' }}>
        {loading && (
          <div className="muted" style={{ textAlign: 'center', padding: 'var(--pad-4)', fontSize: 12 }}>
            Loading…
          </div>
        )}
        {error && (
          <div style={{ color: 'var(--fail)', textAlign: 'center', padding: 'var(--pad-4)', fontSize: 12 }}>
            Failed to load timeline
          </div>
        )}
        {!loading && !error && events.length === 0 && (
          <div className="muted" style={{ textAlign: 'center', padding: 'var(--pad-4)', fontSize: 13 }}>
            No events recorded for this ticket
          </div>
        )}
        {!loading && !error && events.length > 0 && (
          <div style={{ position: 'relative', paddingLeft: 24 }}>
            {/* Vertical line */}
            <div style={{
              position: 'absolute', left: 7, top: 8, bottom: 8,
              width: 2, background: 'var(--border)',
            }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--pad-3)' }}>
              {events.map(ev => {
                const bs = badgeStyle(ev.event_type);
                return (
                  <div key={ev.id} style={{ position: 'relative', display: 'grid', gridTemplateColumns: '1fr', gap: 4 }}>
                    {/* Dot on the line */}
                    <div style={{
                      position: 'absolute', left: -21, top: 6,
                      width: 8, height: 8, borderRadius: '50%',
                      background: bs.color, border: '2px solid var(--bg)',
                      flexShrink: 0,
                    }} />

                    {/* Event card */}
                    <div style={{
                      background: 'var(--bg-2)',
                      border: '1px solid var(--border)',
                      padding: 'var(--pad-2) var(--pad-3)',
                      display: 'flex', flexDirection: 'column', gap: 4,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{
                          fontFamily: 'var(--font-mono)', fontSize: 11,
                          padding: '1px 6px',
                          background: bs.bg, color: bs.color,
                          border: `1px solid ${bs.color}`,
                        }}>
                          {ev.event_type}
                        </span>
                        {ev.role && (
                          <span className="tag muted mono" style={{ fontSize: 10 }}>{ev.role}</span>
                        )}
                        {ev.model && (
                          <span className="muted mono" style={{ fontSize: 10 }}>{ev.model}</span>
                        )}
                        <span className="muted mono" style={{ fontSize: 10, marginLeft: 'auto' }}>
                          {fmtTs(ev.created_at)}
                        </span>
                      </div>
                      {ev.detail && (
                        <div className="muted" style={{ fontSize: 11 }}>{ev.detail}</div>
                      )}
                      {ev.payload && Object.keys(ev.payload).length > 0 && (
                        <pre style={{
                          margin: 0, fontSize: 10, color: 'var(--fg-3)',
                          background: 'var(--bg)', padding: '4px 6px',
                          overflow: 'auto', maxHeight: 120,
                          whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                        }}>
                          {JSON.stringify(ev.payload, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
