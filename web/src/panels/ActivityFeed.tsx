import { useState, useMemo } from 'react';
import type { FeedItem } from '../lib/types';
import { relTime } from '../lib/utils';
import RoleTag from '../components/RoleTag';
import EventGlyph from '../components/EventGlyph';

const ROLES = ['all', 'po', 'dev', 'qa', 'reviewer', 'merge', 'judge'] as const;

interface ActivityFeedProps {
  events: FeedItem[];
}

export default function ActivityFeed({ events }: ActivityFeedProps) {
  const [filter, setFilter] = useState('all');
  const rows = useMemo(() => {
    const r = filter === 'all' ? events : events.filter(e => e.role === filter);
    return r.slice(0, 60);
  }, [events, filter]);

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="panel-h">
        <span>Activity feed</span>
        <span className="actions">
          {ROLES.map(r => (
            <button
              key={r}
              className={`btn ${filter === r ? 'primary' : ''}`}
              onClick={() => setFilter(r)}
            >
              {r}
            </button>
          ))}
        </span>
      </div>
      <div style={{ overflow: 'auto', maxHeight: 480 }}>
        {rows.map(e => {
          const ts = new Date(e.created_at).getTime();
          return (
            <div key={e.id} className="feed-row">
              <EventGlyph event={e.event_type} />
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <RoleTag role={e.role} />
                  <span className="mono" style={{ fontSize: 12 }}>{e.event_type}</span>
                  <span className="muted mono" style={{ fontSize: 11 }}>
                    · {e.project}
                    {e.issue_number != null ? `#${e.issue_number}` : ''}
                  </span>
                </div>
                <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                  <span className="mono">{e.model ?? '—'}</span>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="muted mono" style={{ fontSize: 10 }}>{relTime(ts)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
