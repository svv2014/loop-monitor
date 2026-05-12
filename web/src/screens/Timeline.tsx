import { useEffect, useState } from 'react';
import type { TimelineEvent, TimelineResponse } from '../lib/types';

interface TimelineProps {
  projectId: string;
  issueNum: number;
  onBack: () => void;
}

const TYPE_BADGE: Record<string, { label: string; color: string }> = {
  label_change:    { label: 'label',     color: 'var(--role-po)' },
  reconcile_check: { label: 'reconcile', color: 'var(--fg-3)' },
  handler_run:     { label: 'handler',   color: 'var(--role-dev)' },
  merge:           { label: 'merge',     color: 'var(--role-merge)' },
  pr_opened:       { label: 'pr',        color: 'var(--role-reviewer)' },
  qa_run:          { label: 'qa',        color: 'var(--role-qa)' },
};

function typeBadge(type: string): { label: string; color: string } {
  return TYPE_BADGE[type] ?? { label: type, color: 'var(--fg-2)' };
}

function fmtTs(ts: string): string {
  try {
    const d = new Date(ts.includes('T') ? ts : ts + 'Z');
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return ts;
  }
}

export default function Timeline({ projectId, issueNum, onBack }: TimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [includeSkips, setIncludeSkips] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    const qs = `slug=${encodeURIComponent(projectId)}&num=${issueNum}&include_skips=${includeSkips}`;
    fetch(`/api/timeline?${qs}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: TimelineResponse) => { setEvents(data.events); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [projectId, issueNum, includeSkips]);

  return (
    <div data-testid="timeline">
      {/* Header */}
      <div className="screen-h" style={{ display: 'flex', alignItems: 'center', gap: 'var(--pad-3)', padding: 'var(--pad-2) var(--pad-4)' }}>
        <button className="btn" onClick={onBack}>← Back</button>
        <h1 style={{ flex: 1, margin: 0, fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500, letterSpacing: '0.04em' }}>
          <span className="muted">timeline /</span> {projectId} <span className="muted">·</span> #{issueNum}
        </h1>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer', color: 'var(--fg-2)' }}>
          <input
            type="checkbox"
            checked={includeSkips}
            onChange={e => setIncludeSkips(e.target.checked)}
          />
          show reconcile skips
        </label>
      </div>

      {/* Body */}
      <div style={{ padding: 'var(--pad-4)' }}>
        {loading && (
          <div className="muted" style={{ fontSize: 12 }}>Loading…</div>
        )}
        {error && (
          <div style={{ color: 'var(--fail)', fontSize: 12 }}>Failed to load timeline.</div>
        )}
        {!loading && !error && events.length === 0 && (
          <div className="muted" style={{ fontSize: 12, textAlign: 'center', padding: 'var(--pad-4)' }}>
            No events recorded for this ticket.
          </div>
        )}
        {!loading && !error && events.length > 0 && (
          <div style={{ position: 'relative', paddingLeft: 24 }}>
            {/* Vertical connector line */}
            <div style={{
              position: 'absolute', left: 7, top: 8, bottom: 8,
              width: 2, background: 'var(--border)',
            }} />

            {events.map((ev, idx) => {
              const badge = typeBadge(ev.type);
              return (
                <div key={ev.id} style={{ position: 'relative', marginBottom: idx < events.length - 1 ? 20 : 0 }}>
                  {/* Dot */}
                  <div style={{
                    position: 'absolute', left: -20, top: 3,
                    width: 8, height: 8,
                    borderRadius: '50%',
                    background: badge.color,
                    border: '2px solid var(--bg)',
                  }} />

                  <div className="panel" style={{ padding: 'var(--pad-2) var(--pad-3)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: ev.payload ? 6 : 0 }}>
                      <span className="tag" style={{ color: badge.color, borderColor: badge.color, fontSize: 10 }}>
                        {badge.label}
                      </span>
                      <span className="mono muted" style={{ fontSize: 11 }}>{fmtTs(ev.ts)}</span>
                      {ev.pr_number != null && (
                        <span className="muted" style={{ fontSize: 11 }}>PR #{ev.pr_number}</span>
                      )}
                    </div>

                    {ev.payload && (
                      <pre style={{
                        margin: 0,
                        fontSize: 11,
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--fg-2)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                      }}>
                        {JSON.stringify(ev.payload, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
