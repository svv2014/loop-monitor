import { useEffect, useState } from 'react';
import type { TimelineEvent, TimelineResponse } from '../lib/types';

interface TimelineProps {
  projectId: string;
  ticketNum: number | null;
  onBack: () => void;
}

const TYPE_BADGE: Record<string, { label: string; color: string }> = {
  dev_start:       { label: 'dev:start',    color: 'var(--role-dev)' },
  dev_done:        { label: 'dev:done',     color: 'var(--role-dev)' },
  dev_failed:      { label: 'dev:fail',     color: 'var(--fail,#ef4444)' },
  qa_start:        { label: 'qa:start',     color: 'var(--role-qa)' },
  qa_pass:         { label: 'qa:pass',      color: 'var(--role-qa)' },
  qa_fail:         { label: 'qa:fail',      color: 'var(--fail,#ef4444)' },
  review_start:    { label: 'review:start', color: 'var(--role-reviewer)' },
  review_done:     { label: 'review:done',  color: 'var(--role-reviewer)' },
  review_failed:   { label: 'review:fail',  color: 'var(--fail,#ef4444)' },
  merge_start:     { label: 'merge:start',  color: 'var(--role-merge)' },
  merge_done:      { label: 'merge:done',   color: 'var(--role-merge)' },
  po_start:        { label: 'po:start',     color: 'var(--role-po)' },
  po_done:         { label: 'po:done',      color: 'var(--role-po)' },
  po_failed:       { label: 'po:fail',      color: 'var(--fail,#ef4444)' },
  rework_start:    { label: 'rework',       color: 'var(--fg-3)' },
  rework_done:     { label: 'rework:done',  color: 'var(--fg-2)' },
  reconcile_check: { label: 'reconcile',    color: 'var(--fg-3)' },
  label_change:    { label: 'label',        color: 'var(--accent2,#7c3aed)' },
};

function getTypeBadge(eventType: string): { label: string; color: string } {
  if (TYPE_BADGE[eventType]) return TYPE_BADGE[eventType];
  if (eventType.endsWith('_done') || eventType.endsWith('_pass')) {
    return { label: eventType, color: 'var(--role-merge)' };
  }
  if (eventType.endsWith('_fail') || eventType.endsWith('_failed')) {
    return { label: eventType, color: 'var(--fail,#ef4444)' };
  }
  if (eventType.endsWith('_start')) {
    return { label: eventType, color: 'var(--fg-2)' };
  }
  return { label: eventType, color: 'var(--fg-3)' };
}

function fmtTs(ts: string): string {
  try {
    const d = new Date(ts.includes('T') ? ts : ts + 'Z');
    return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  } catch {
    return ts;
  }
}

export default function Timeline({ projectId, ticketNum, onBack }: TimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [includeSkips, setIncludeSkips] = useState(false);

  useEffect(() => {
    if (!projectId || ticketNum == null) {
      setEvents([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const p = new URLSearchParams({ slug: projectId, num: String(ticketNum) });
    if (includeSkips) p.set('include_skips', 'true');
    fetch(`/api/timeline?${p.toString()}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: TimelineResponse) => { setEvents(data.events); setLoading(false); })
      .catch(() => { setEvents([]); setLoading(false); });
  }, [projectId, ticketNum, includeSkips]);

  return (
    <div data-testid="timeline">
      <div className="screen-h" style={{ display: 'flex', alignItems: 'center', gap: 'var(--pad-3)', padding: 'var(--pad-2) var(--pad-4)' }}>
        <button className="btn" onClick={onBack}>← Back</button>
        <h1 style={{ flex: 1, margin: 0, fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500, letterSpacing: '0.04em' }}>
          <span className="muted">timeline /</span> {projectId}
          {ticketNum != null && (
            <span className="muted"> / <span style={{ color: 'var(--fg)' }}>#{ticketNum}</span></span>
          )}
        </h1>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={includeSkips}
            onChange={e => setIncludeSkips(e.target.checked)}
          />
          <span className="muted">Show skip noise</span>
        </label>
      </div>

      <div style={{ padding: 'var(--pad-4)' }}>
        {loading ? (
          <div className="muted" style={{ fontSize: 12 }}>Loading…</div>
        ) : events.length === 0 ? (
          <div className="muted" style={{ fontSize: 13 }}>No events recorded for this ticket.</div>
        ) : (
          <div style={{ position: 'relative', paddingLeft: 24 }}>
            <div style={{
              position: 'absolute', left: 8, top: 8, bottom: 8,
              width: 2, background: 'var(--border)',
            }} />
            {events.map((e, i) => {
              const badge = getTypeBadge(e.type);
              return (
                <div key={e.id ?? i} style={{ position: 'relative', marginBottom: 'var(--pad-3)', paddingLeft: 'var(--pad-3)' }}>
                  <div style={{
                    position: 'absolute', left: -20, top: 6,
                    width: 8, height: 8, borderRadius: '50%',
                    background: badge.color, border: '2px solid var(--bg)',
                  }} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span className="tag" style={{ color: badge.color, borderColor: 'currentColor', flexShrink: 0 }}>
                      {badge.label}
                    </span>
                    {e.role && (
                      <span className="muted mono" style={{ fontSize: 11 }}>{e.role}</span>
                    )}
                    {(e.issue_number != null || e.pr_number != null) && (
                      <span className="muted mono" style={{ fontSize: 11 }}>
                        {e.issue_number != null ? `#${e.issue_number}` : `PR#${e.pr_number}`}
                      </span>
                    )}
                    <span className="muted mono" style={{ fontSize: 11, marginLeft: 'auto' }}>
                      {fmtTs(e.ts)}
                    </span>
                  </div>
                  {e.detail && (
                    <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{e.detail}</div>
                  )}
                  {e.payload != null && Object.keys(e.payload).length > 0 && (
                    <pre className="mono muted" style={{
                      fontSize: 10, marginTop: 4, padding: '4px 8px',
                      background: 'var(--bg-2)', overflow: 'auto',
                      maxHeight: 80, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                    }}>
                      {JSON.stringify(e.payload, null, 2)}
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
