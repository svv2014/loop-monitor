import { useState, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import Drawer from '../components/Drawer';
import RoleTag from '../components/RoleTag';
import EventGlyph from '../components/EventGlyph';
import { fetchTimeline } from '../lib/api';
import type { Timeline as TimelineData, TimelineEvent } from '../lib/types';
import { relTime, durationFmt } from '../lib/utils';

// Parse hash for timeline key: #...&timeline=<project>/<kind>/<n>
function parseTimelineHash(hash: string): { project: string; kind: 'issue' | 'pr'; number: number } | null {
  if (!hash) return null;
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  const params = new URLSearchParams(raw);
  const val = params.get('timeline');
  if (!val) return null;
  const parts = val.split('/');
  if (parts.length < 3) return null;
  const [project, kind, numStr] = parts;
  if (kind !== 'issue' && kind !== 'pr') return null;
  const number = parseInt(numStr, 10);
  if (isNaN(number)) return null;
  return { project, kind, number };
}

function clearTimelineHash(): void {
  const raw = window.location.hash.startsWith('#')
    ? window.location.hash.slice(1)
    : window.location.hash;
  const params = new URLSearchParams(raw);
  params.delete('timeline');
  const str = params.toString();
  history.replaceState(
    null,
    '',
    window.location.pathname + window.location.search + (str ? `#${str}` : ''),
  );
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

function setTimelineHash(project: string, kind: 'issue' | 'pr', number: number): void {
  const raw = window.location.hash.startsWith('#')
    ? window.location.hash.slice(1)
    : window.location.hash;
  const params = new URLSearchParams(raw);
  params.set('timeline', `${project}/${kind}/${number}`);
  history.replaceState(
    null,
    '',
    window.location.pathname + window.location.search + `#${params.toString()}`,
  );
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

const DT_STYLE: React.CSSProperties = {
  color: 'var(--fg-3)',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  alignSelf: 'center',
};

function EventRow({ ev }: { ev: TimelineEvent }) {
  const ts = new Date(ev.created_at).getTime();
  return (
    <div className="feed-row" style={{ alignItems: 'flex-start' }}>
      <EventGlyph event={ev.event_type} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <RoleTag role={ev.role} />
          <span className="mono" style={{ fontSize: 12 }}>{ev.event_type}</span>
          {ev.model && (
            <span className="muted mono" style={{ fontSize: 11 }}>{ev.model}</span>
          )}
        </div>
        {ev.detail && (
          <div className="muted" style={{ fontSize: 11, marginTop: 2, wordBreak: 'break-word' }}>
            {ev.detail}
          </div>
        )}
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        {ev.duration_seconds != null && (
          <div className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>
            {durationFmt(ev.duration_seconds * 1000)}
          </div>
        )}
        <div className="muted mono" style={{ fontSize: 10 }}>{relTime(ts)}</div>
      </div>
    </div>
  );
}

function TotalsRow({ data }: { data: TimelineData }) {
  const t = data.totals;
  return (
    <div style={{
      borderTop: '1px solid var(--border)',
      paddingTop: 'var(--pad-3)',
      display: 'grid',
      gridTemplateColumns: 'auto 1fr',
      gap: '6px var(--pad-3)',
      fontSize: 12,
    }}>
      {t.total_duration_seconds != null && (
        <>
          <dt style={DT_STYLE}>Total time</dt>
          <dd style={{ margin: 0 }} className="mono">
            {durationFmt(t.total_duration_seconds * 1000)}
          </dd>
        </>
      )}
      {t.total_points != null && t.total_points > 0 && (
        <>
          <dt style={DT_STYLE}>Points</dt>
          <dd className="mono" style={{ margin: 0, color: 'var(--accent)' }}>
            +{t.total_points}
          </dd>
        </>
      )}
      {t.rework_count > 0 && (
        <>
          <dt style={DT_STYLE}>Rework</dt>
          <dd className="mono" style={{ margin: 0, color: 'var(--role-err)' }}>
            {t.rework_count}×
          </dd>
        </>
      )}
      {t.verdict && (
        <>
          <dt style={DT_STYLE}>Verdict</dt>
          <dd style={{ margin: 0 }} className="mono">{t.verdict}</dd>
        </>
      )}
    </div>
  );
}

interface TimelinePanelInnerProps {
  project: string;
  kind: 'issue' | 'pr';
  number: number;
  onClose: () => void;
}

function TimelinePanelInner({ project, kind, number, onClose }: TimelinePanelInnerProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['timeline', project, kind, number],
    queryFn: () => fetchTimeline(project, kind, number),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  // Active tab: 'current' or 'linked'
  const [tab, setTab] = useState<'current' | 'linked'>('current');

  const hasLinked = data && (
    (data.kind === 'issue' && data.linked_pr != null) ||
    (data.kind === 'pr' && data.linked_issue != null)
  );

  const linkedKind: 'issue' | 'pr' = data?.kind === 'issue' ? 'pr' : 'issue';
  const linkedNumber = data?.kind === 'issue' ? data?.linked_pr : data?.linked_issue;

  // Linked tab query — only runs when tab='linked' and linked exists
  const linkedQuery = useQuery({
    queryKey: ['timeline', project, linkedKind, linkedNumber],
    queryFn: () => fetchTimeline(project, linkedKind, linkedNumber!),
    enabled: tab === 'linked' && linkedNumber != null,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const activeData = tab === 'linked' ? linkedQuery.data : data;
  const activeLoading = tab === 'linked' ? linkedQuery.isLoading : isLoading;

  const drawerTitle = data
    ? `${data.project} ${data.kind} #${data.number}${data.title ? ` — ${data.title}` : ''}`
    : `${project} ${kind} #${number}`;

  return (
    <Drawer open={true} onClose={onClose} title={drawerTitle}>
      {/* Header meta */}
      {data && (
        <div style={{ display: 'flex', gap: 'var(--pad-2)', alignItems: 'center', flexWrap: 'wrap' }}>
          <a
            href={data.github_url}
            target="_blank"
            rel="noreferrer"
            className="btn"
            style={{ fontSize: 11, textDecoration: 'none' }}
          >
            GitHub ↗
          </a>
          {data.stage && (
            <span
              className="tag mono"
              style={{ fontSize: 11, background: 'var(--bg-3)', color: 'var(--fg-2)' }}
            >
              {data.stage}
            </span>
          )}
        </div>
      )}

      {/* Tabs for linked ticket */}
      {hasLinked && data && (
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            className={`btn ${tab === 'current' ? 'primary' : ''}`}
            onClick={() => setTab('current')}
            style={{ fontSize: 11 }}
          >
            {data.kind} #{data.number}
          </button>
          <button
            className={`btn ${tab === 'linked' ? 'primary' : ''}`}
            onClick={() => setTab('linked')}
            style={{ fontSize: 11 }}
          >
            {linkedKind} #{linkedNumber}
          </button>
        </div>
      )}

      <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: 0 }} />

      {/* Events list */}
      {activeLoading ? (
        <div className="muted" style={{ fontSize: 12 }}>Loading timeline…</div>
      ) : isError ? (
        <div style={{ fontSize: 12, color: 'var(--role-err)' }}>Failed to load timeline.</div>
      ) : !activeData || activeData.events.length === 0 ? (
        <div className="muted" style={{ fontSize: 12 }}>No events recorded</div>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {activeData.events.map(ev => (
              <EventRow key={ev.id} ev={ev} />
            ))}
          </div>
          <TotalsRow data={activeData} />
        </>
      )}
    </Drawer>
  );
}

export default function Timeline() {
  const [parsed, setParsed] = useState(() => parseTimelineHash(window.location.hash));

  const refresh = useCallback(() => {
    setParsed(parseTimelineHash(window.location.hash));
  }, []);

  useEffect(() => {
    window.addEventListener('hashchange', refresh);
    return () => window.removeEventListener('hashchange', refresh);
  }, [refresh]);

  function handleClose() {
    clearTimelineHash();
  }

  if (!parsed) return null;

  return (
    <TimelinePanelInner
      project={parsed.project}
      kind={parsed.kind}
      number={parsed.number}
      onClose={handleClose}
    />
  );
}

// Export helper for other components to open the timeline
export { setTimelineHash };
