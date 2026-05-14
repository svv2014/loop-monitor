import { useEffect, useState } from 'react';

interface TimelineEvent {
  id: number;
  ts: string;
  type: string;
  role: string;
  model: string | null;
  issue_number: number | null;
  pr_number: number | null;
  detail: string | null;
  payload: Record<string, unknown> | string | null;
  loop_id: string | null;
}

interface TimelineResponse {
  events: TimelineEvent[];
}

const TYPE_BADGE: Record<string, { label: string; color: string }> = {
  dev_start:        { label: 'dev',       color: 'var(--role-dev)'      },
  dev_done:         { label: 'dev ✓',     color: 'var(--role-dev)'      },
  dev_failed:       { label: 'dev ✗',     color: 'var(--fail,#ef4444)'  },
  review_start:     { label: 'review',    color: 'var(--role-reviewer)' },
  review_done:      { label: 'review ✓',  color: 'var(--role-reviewer)' },
  review_failed:    { label: 'review ✗',  color: 'var(--fail,#ef4444)'  },
  qa_start:         { label: 'qa',        color: 'var(--role-qa)'       },
  qa_pass:          { label: 'qa ✓',      color: 'var(--role-qa)'       },
  qa_fail:          { label: 'qa ✗',      color: 'var(--fail,#ef4444)'  },
  merge_start:      { label: 'merge',     color: 'var(--role-merge)'    },
  merge_done:       { label: 'merge ◆',   color: 'var(--role-merge)'    },
  po_start:         { label: 'po',        color: 'var(--role-po)'       },
  po_done:          { label: 'po ✓',      color: 'var(--role-po)'       },
  po_failed:        { label: 'po ✗',      color: 'var(--fail,#ef4444)'  },
  judge_done:       { label: 'judge ★',   color: 'var(--role-judge)'    },
  reconcile_check:  { label: 'reconcile', color: 'var(--fg-3)'          },
  label_change:     { label: 'label',     color: 'var(--accent2,#7c3aed)' },
  handler_run:      { label: 'handler',   color: 'var(--accent2,#7c3aed)' },
};

function getBadge(type: string): { label: string; color: string } {
  return TYPE_BADGE[type] ?? { label: type, color: 'var(--fg-3)' };
}

function fmtTs(ts: string): string {
  try {
    const d = new Date(ts.includes('T') ? ts : ts + 'Z');
    return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  } catch {
    return ts;
  }
}

interface TimelineProps {
  slug: string;
  num: number;
  onBack: () => void;
}

export default function Timeline({ slug, num, onBack }: TimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [includeSkips, setIncludeSkips] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    fetch(`/api/timeline?slug=${encodeURIComponent(slug)}&num=${num}&include_skips=${includeSkips}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: TimelineResponse) => { setEvents(data.events); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [slug, num, includeSkips]);

  return (
    <div data-testid="timeline">
      <div className="screen-h" style={{ display: 'flex', alignItems: 'center', gap: 'var(--pad-3)', padding: 'var(--pad-2) var(--pad-4)' }}>
        <button className="btn" onClick={onBack}>← Back</button>
        <h1 style={{ flex: 1, margin: 0, fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500, letterSpacing: '0.04em' }}>
          <span className="muted">timeline /</span> {slug} <span className="muted">·</span> #{num}
        </h1>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={includeSkips}
            onChange={e => setIncludeSkips(e.target.checked)}
          />
          <span className="muted">Show reconcile skips</span>
        </label>
      </div>

      <div style={{ padding: 'var(--pad-4)' }}>
        {loading && (
          <div className="muted" style={{ textAlign: 'center', padding: 'var(--pad-4)', fontSize: 12 }}>Loading…</div>
        )}
        {error && (
          <div className="muted" style={{ textAlign: 'center', padding: 'var(--pad-4)', fontSize: 12, color: 'var(--fail,#ef4444)' }}>
            Failed to load timeline
          </div>
        )}
        {!loading && !error && events.length === 0 && (
          <div className="muted" style={{ textAlign: 'center', padding: 'var(--pad-4)', fontSize: 12 }}>
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
            {events.map((ev, idx) => {
              const badge = getBadge(ev.type);
              return (
                <div key={ev.id ?? idx} style={{ position: 'relative', marginBottom: 18 }}>
                  {/* Dot */}
                  <div style={{
                    position: 'absolute', left: -20, top: 4,
                    width: 8, height: 8,
                    borderRadius: '50%',
                    background: badge.color,
                    border: '2px solid var(--bg)',
                  }} />
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, flexWrap: 'wrap' }}>
                    <span className="tag" style={{ color: badge.color, borderColor: 'currentColor', flexShrink: 0 }}>
                      {badge.label}
                    </span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)', flexShrink: 0, paddingTop: 2 }}>
                      {fmtTs(ev.ts)}
                    </span>
                    {ev.role && (
                      <span className="muted mono" style={{ fontSize: 11, paddingTop: 2 }}>{ev.role}</span>
                    )}
                    {ev.detail && (
                      <span className="muted" style={{ fontSize: 11, paddingTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 400 }}
                        title={ev.detail}>
                        {ev.detail}
                      </span>
                    )}
                  </div>
                  {ev.payload && typeof ev.payload === 'object' && Object.keys(ev.payload).length > 0 && (
                    <pre style={{
                      margin: '4px 0 0',
                      padding: '4px 8px',
                      background: 'var(--bg-2)',
                      fontSize: 10,
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--fg-3)',
                      overflow: 'auto',
                      maxHeight: 80,
                    }}>
                      {JSON.stringify(ev.payload, null, 2)}
                    </pre>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
