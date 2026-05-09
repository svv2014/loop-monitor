// TODO(#113): wire visual-diff once harness lands
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchActive, fetchFeed, fetchHistory, fetchEventsGraph } from '../lib/api';
import { buildProjectStatus, build24hBuckets } from '../lib/transforms';
import type { LoopEvent } from '../lib/types';
import NowStrip from '../panels/NowStrip';
import Activity24h from '../panels/Activity24h';
import ProjectCard from '../panels/ProjectCard';
import Leaderboard from '../panels/Leaderboard';
import ActivityFeed from '../panels/ActivityFeed';
import EventGlyph from '../components/EventGlyph';
import RoleTag from '../components/RoleTag';
import { relTime, durationFmt } from '../lib/utils';
import Charts from '../panels/Charts';
import ClaudeUsage from '../panels/ClaudeUsage';
import HealthPanel from '../panels/HealthPanel';

const COMPLETED_TYPES = new Set([
  'merge_done', 'judge_done', 'review_done', 'dev_done', 'po_done',
]);

export default function Overview() {
  const { data: workers = [] } = useQuery({
    queryKey: ['active'],
    queryFn: () => fetchActive(),
    refetchInterval: 5_000,
    staleTime: 0,
  });

  const { data: feed = [] } = useQuery({
    queryKey: ['feed'],
    queryFn: () => fetchFeed(),
    refetchInterval: 5_000,
    staleTime: 0,
  });

  const { data: history = [] } = useQuery({
    queryKey: ['history'],
    queryFn: () => fetchHistory(),
    refetchInterval: 5_000,
    staleTime: 0,
  });

  const { data: eventsGraph } = useQuery({
    queryKey: ['eventsGraph'],
    queryFn: () => fetchEventsGraph(24),
    refetchInterval: 60_000,
    staleTime: 0,
  });

  const buckets = useMemo(() => {
    if (eventsGraph) {
      // Bucket by relative hour from now (slot 23 = current hour, slot 0 = 23h ago).
      // `b.hour` from /api/events_graph is a UTC ISO string with no Z suffix; append Z so JS parses as UTC.
      const buckets = Array.from({ length: 24 }, (_, i) => ({
        hour: i,
        counts: {} as Record<string, number>,
        total: 0,
      }));
      const now = Date.now();
      for (const b of eventsGraph.buckets) {
        const ts = new Date(b.hour + 'Z').getTime();
        const hoursAgo = Math.floor((now - ts) / (60 * 60 * 1000));
        if (hoursAgo < 0 || hoursAgo >= 24) continue;
        const idx = 23 - hoursAgo;
        buckets[idx].counts[b.role] = (buckets[idx].counts[b.role] ?? 0) + b.count;
        buckets[idx].total += b.count;
      }
      return buckets;
    }
    return build24hBuckets(history as (LoopEvent & { ts?: number })[]);
  }, [eventsGraph, history]);

  const projects = useMemo(
    () => buildProjectStatus(
      history as Parameters<typeof buildProjectStatus>[0],
      workers,
    ),
    [history, workers],
  );

  const completed = useMemo(
    () => history.filter(e => COMPLETED_TYPES.has(e.event_type)).slice(0, 30),
    [history],
  );

  return (
    <>
      <NowStrip workers={workers} events={feed} />
      <div style={{ padding: 'var(--pad-4)', display: 'grid', gap: 'var(--pad-3)' }}>

        <Activity24h buckets={buckets} />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 'var(--pad-3)' }}>
          <div className="panel">
            <div className="panel-h">
              <span>Project status · {projects.length}</span>
              <span className="muted">
                {projects.filter(p => p.status === 'busy').length} busy
              </span>
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 1,
              background: 'var(--border)',
            }}>
              {projects.map(p => (
                <ProjectCard key={p.id} p={p} onClick={() => undefined} />
              ))}
            </div>
          </div>
          <div style={{ display: 'grid', gap: 'var(--pad-3)', alignContent: 'start' }}>
            <Leaderboard events={history} />
            <HealthPanel />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--pad-3)' }}>
          <ActivityFeed events={feed} />
          <div className="panel">
            <div className="panel-h"><span>Completed jobs · last 30</span></div>
            <div style={{ overflow: 'auto', maxHeight: 480 }}>
              {completed.map(e => {
                const ts = new Date(e.created_at).getTime();
                const durMs = (e.duration_seconds ?? 0) * 1000;
                return (
                  <div key={e.id} className="feed-row">
                    <EventGlyph event={e.event_type} />
                    <div>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span
                          className="mono"
                          style={{ color: `var(--role-${e.role})`, fontWeight: 500 }}
                        >
                          {e.project}
                        </span>
                        <RoleTag role={e.role} />
                        <span className="muted mono" style={{ fontSize: 11 }}>{e.model}</span>
                      </div>
                      <div className="muted mono" style={{ fontSize: 11, marginTop: 2 }}>
                        {e.event_type}
                        {e.issue_number != null ? ` · #${e.issue_number}` : ''}
                        {durMs > 0 ? ` · ${durationFmt(durMs)}` : ''}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      {(e.points ?? 0) > 0 && (
                        <div className="mono" style={{ color: 'var(--accent)', fontSize: 12 }}>
                          +{e.points}
                        </div>
                      )}
                      <div className="muted mono" style={{ fontSize: 10 }}>{relTime(ts)}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <ClaudeUsage />
        <Charts />

      </div>
    </>
  );
}
