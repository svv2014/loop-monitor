import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Drawer from '../components/Drawer';
import EventGlyph from '../components/EventGlyph';
import RoleTag from '../components/RoleTag';
import { fetchTimeline } from '../lib/api';
import type { Timeline as TimelineData, TimelineEvent } from '../lib/types';
import { durationFmt, parseServerTs, relTime } from '../lib/utils';

function parseTimelineHash(hash: string): { project: string; kind: 'issue' | 'pr'; number: number } | null {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  const params = new URLSearchParams(raw);
  const value = params.get('timeline');
  if (!value) return null;
  const [project, kind, numberRaw] = value.split('/');
  const number = Number(numberRaw);
  if (!project || (kind !== 'issue' && kind !== 'pr') || !Number.isInteger(number)) return null;
  return { project, kind, number };
}

function clearTimelineHash() {
  const raw = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash;
  const params = new URLSearchParams(raw);
  params.delete('timeline');
  const next = params.toString();
  history.replaceState(null, '', window.location.pathname + window.location.search + (next ? `#${next}` : ''));
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

function EventRow({ event }: { event: TimelineEvent }) {
  const ts = parseServerTs(event.created_at);
  return (
    <div className="feed-row" style={{ alignItems: 'flex-start' }}>
      <EventGlyph event={event.event_type} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <RoleTag role={event.role} />
          <span className="mono" style={{ fontSize: 12 }}>{event.event_type}</span>
          {event.model && <span className="muted mono" style={{ fontSize: 11 }}>{event.model}</span>}
          {event.points != null && event.points > 0 && (
            <span className="tag mono" style={{ color: 'var(--accent)' }}>+{event.points}</span>
          )}
        </div>
        {event.detail && (
          <div className="muted" style={{ fontSize: 11, marginTop: 2, wordBreak: 'break-word' }}>
            {event.detail}
          </div>
        )}
      </div>
      <div className="mono muted" style={{ fontSize: 10, textAlign: 'right', flexShrink: 0 }}>
        {event.duration_seconds != null && (
          <div style={{ color: 'var(--fg-2)' }}>{durationFmt(event.duration_seconds * 1000)}</div>
        )}
        <div>{relTime(ts)}</div>
      </div>
    </div>
  );
}

function TimelineBody({ data }: { data: TimelineData }) {
  return (
    <>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <a className="btn" href={data.github_url} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
          GitHub
        </a>
        {data.stage && <span className="tag mono">{data.stage}</span>}
      </div>
      {data.events.length === 0 ? (
        <div className="muted" style={{ fontSize: 12 }}>No events recorded</div>
      ) : (
        <div>{data.events.map((event) => <EventRow key={event.id} event={event} />)}</div>
      )}
      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 'var(--pad-3)', fontSize: 12 }}>
        <div className="mono">Total time: {data.totals.total_duration_seconds == null ? 'n/a' : durationFmt(data.totals.total_duration_seconds * 1000)}</div>
        <div className="mono">Points: {data.totals.total_points}</div>
        <div className="mono">Rework: {data.totals.rework_count}</div>
        {data.totals.verdict && <div className="mono">Verdict: {data.totals.verdict}</div>}
      </div>
    </>
  );
}

export default function TimelinePanel() {
  const [target, setTarget] = useState(() => parseTimelineHash(window.location.hash));

  useEffect(() => {
    const onHash = () => setTarget(parseTimelineHash(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const query = useQuery({
    queryKey: ['timeline-panel', target?.project, target?.kind, target?.number],
    queryFn: () => fetchTimeline(target!.project, target!.kind, target!.number),
    enabled: target != null,
    staleTime: 30_000,
  });

  if (!target) return null;

  const title = query.data?.title
    ? `${query.data.project} ${query.data.kind} #${query.data.number} - ${query.data.title}`
    : `${target.project} ${target.kind} #${target.number}`;

  return (
    <Drawer open={true} onClose={clearTimelineHash} title={title}>
      {query.isLoading ? (
        <div className="muted" style={{ fontSize: 12 }}>Loading timeline...</div>
      ) : query.isError || !query.data ? (
        <div style={{ fontSize: 12, color: 'var(--fail)' }}>Failed to load timeline</div>
      ) : (
        <TimelineBody data={query.data} />
      )}
    </Drawer>
  );
}
