import { useEffect, useState } from 'react';
import { fetchTimeline } from '../lib/api';
import type { TimelineEvent } from '../lib/types';

interface TimelineProps {
  projectId: string;
  issueNum: number;
  onBack: () => void;
}

const TYPE_BADGE: Record<string, { label: string; color: string }> = {
  dev_start:        { label: 'dev',       color: 'var(--role-dev)' },
  dev_done:         { label: 'dev',       color: 'var(--role-dev)' },
  dev_failed:       { label: 'dev',       color: 'var(--fail)' },
  review_start:     { label: 'review',    color: 'var(--role-reviewer)' },
  review_done:      { label: 'review',    color: 'var(--role-reviewer)' },
  review_failed:    { label: 'review',    color: 'var(--fail)' },
  qa_start:         { label: 'qa',        color: 'var(--role-qa)' },
  qa_pass:          { label: 'qa',        color: 'var(--role-qa)' },
  qa_fail:          { label: 'qa',        color: 'var(--fail)' },
  merge_start:      { label: 'merge',     color: 'var(--role-merge)' },
  merge_done:       { label: 'merge',     color: 'var(--role-merge)' },
  po_start:         { label: 'po',        color: 'var(--role-po)' },
  po_done:          { label: 'po',        color: 'var(--role-po)' },
  po_failed:        { label: 'po',        color: 'var(--fail)' },
  rework_start:     { label: 'rework',    color: 'var(--fg-3)' },
  rework_done:      { label: 'rework',    color: 'var(--fg-3)' },
  reconcile_check:  { label: 'reconcile', color: 'var(--fg-3)' },
  judge:            { label: 'judge',     color: 'var(--role-judge)' },
};

function badgeFor(eventType: string): { label: string; color: string } {
  if (TYPE_BADGE[eventType]) return TYPE_BADGE[eventType];
  // Derive from suffix pattern
  if (eventType.endsWith('_done') || eventType.endsWith('_pass')) return { label: eventType, color: 'var(--accent)' };
  if (eventType.endsWith('_failed') || eventType.endsWith('_fail')) return { label: eventType, color: 'var(--fail)' };
  if (eventType.endsWith('_start')) return { label: eventType, color: 'var(--fg-2)' };
  return { label: eventType, color: 'var(--fg-3)' };
}

function fmtTs(isoStr: string): string {
  try {
    const d = new Date(isoStr.includes('T') ? isoStr : isoStr + 'Z');
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return isoStr;
  }
}

function EventRow({ event }: { event: TimelineEvent }) {
  const badge = badgeFor(event.event_type);
  const hasPayload = event.payload && Object.keys(event.payload).length > 0;

  return (
    <div style={{ display: 'flex', gap: 12, padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
      {/* Timeline spine */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, width: 16 }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%',
          background: badge.color,
          flexShrink: 0,
          marginTop: 3,
        }} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="tag" style={{ color: badge.color, borderColor: badge.color, flexShrink: 0 }}>
            {badge.label}
          </span>
          <span className="mono" style={{ fontSize: 12, color: 'var(--fg)' }}>{event.event_type}</span>
          {event.role && event.role !== badge.label && (
            <span className="muted mono" style={{ fontSize: 11 }}>· {event.role}</span>
          )}
          {event.model && (
            <span className="muted mono" style={{ fontSize: 11 }}>· {event.model}</span>
          )}
          {event.pr_number != null && (
            <span className="muted mono" style={{ fontSize: 11 }}>· PR #{event.pr_number}</span>
          )}
        </div>
        {event.detail && (
          <div className="muted" style={{ fontSize: 11, marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {event.detail}
          </div>
        )}
        {hasPayload && (
          <div className="muted mono" style={{ fontSize: 10, marginTop: 3, color: 'var(--fg-3)' }}>
            {Object.entries(event.payload as Record<string, unknown>)
              .slice(0, 4)
              .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
              .join(' · ')}
          </div>
        )}
      </div>

      {/* Timestamp */}
      <div className="muted mono" style={{ fontSize: 10, textAlign: 'right', flexShrink: 0, paddingTop: 3 }}>
        {fmtTs(event.ts)}
      </div>
    </div>
  );
}

export default function Timeline({ projectId, issueNum, onBack }: TimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [includeSkips, setIncludeSkips] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    fetchTimeline(projectId, issueNum, includeSkips)
      .then(data => { setEvents(data.events); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [projectId, issueNum, includeSkips]);

  return (
    <div data-testid="timeline-screen">
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
          Show reconcile skips
        </label>
      </div>

      {/* Body */}
      <div style={{ padding: 'var(--pad-4)' }}>
        <div className="panel">
          <div className="panel-h">
            <span>Event timeline</span>
            {!loading && <span className="muted">{events.length} event{events.length !== 1 ? 's' : ''}</span>}
          </div>
          <div style={{ padding: '0 var(--pad-4)' }}>
            {loading && (
              <div className="muted" style={{ padding: 'var(--pad-3)', textAlign: 'center', fontSize: 12 }}>Loading…</div>
            )}
            {error && (
              <div style={{ padding: 'var(--pad-3)', textAlign: 'center', fontSize: 12, color: 'var(--fail)' }}>Failed to load timeline</div>
            )}
            {!loading && !error && events.length === 0 && (
              <div className="muted" style={{ padding: 'var(--pad-3)', textAlign: 'center', fontSize: 12 }}>
                No events recorded for this ticket
              </div>
            )}
            {!loading && !error && events.map(e => (
              <EventRow key={e.id} event={e} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
