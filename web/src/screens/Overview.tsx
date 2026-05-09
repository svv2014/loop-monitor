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

const COMPLETED_EVENT_TYPES = new Set([
  'merge_done', 'judge_done', 'review_done', 'dev_done', 'po_done',
]);

interface OverviewProps {
  setSelectedProject?: (id: string) => void;
  setScreen?: (screen: string) => void;
}

export default function Overview({ setSelectedProject, setScreen }: OverviewProps) {
  const { data: workers = [] } = useQuery({
    queryKey: ['active'],
    queryFn: () => fetchActive(),
  });

  const { data: feed = [] } = useQuery({
    queryKey: ['feed'],
    queryFn: () => fetchFeed(),
  });

  const { data: history = [] } = useQuery({
    queryKey: ['history'],
    queryFn: () => fetchHistory(),
  });

  const { data: eventsGraph } = useQuery({
    queryKey: ['eventsGraph'],
    queryFn: () => fetchEventsGraph(24),
  });

  const buckets = useMemo(() => {
    if (eventsGraph) {
      // Convert EventsGraph (row-per-role-per-hour) to HourBucket[].
      const map = new Map<number, { hour: number; counts: Record<string, number>; total: number }>();
      for (let h = 0; h < 24; h++) {
        map.set(h, { hour: h, counts: {}, total: 0 });
      }
      for (const b of eventsGraph.buckets) {
        const hourNum = new Date(b.hour).getHours();
        const bucket = map.get(hourNum);
        if (bucket) {
          bucket.counts[b.role] = (bucket.counts[b.role] ?? 0) + b.count;
          bucket.total += b.count;
        }
      }
      return Array.from(map.values());
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
    () => history.filter(e => COMPLETED_EVENT_TYPES.has(e.event_type)).slice(0, 30),
    [history],
  );

  const handleProjectClick = (id: string) => {
    setSelectedProject?.(id);
    setScreen?.('project');
  };

  return (
    <>
      <NowStrip workers={workers} events={feed} />
      <div style={{ padding: 'var(--pad-4)', display: 'grid', gap: 'var(--pad-3)' }}>

        <Activity24h buckets={buckets} />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 'var(--pad-3)' }}>
          <div className="panel">
            <div className="panel-h">
              <span>Project status · {projects.length}</span>
              <span className="muted">{projects.filter(p => p.status === 'busy').length} busy</span>
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 1,
              background: 'var(--border)',
            }}>
              {projects.map(p => (
                <ProjectCard key={p.id} p={p} onClick={() => handleProjectClick(p.id)} />
              ))}
            </div>
          </div>
          <Leaderboard events={history} />
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
                        <span className="mono" style={{ color: `var(--role-${e.role})`, fontWeight: 500 }}>
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

      </div>
    </>
  );
}
