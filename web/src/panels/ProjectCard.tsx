import type { ProjectStatusRow } from '../lib/transforms';
import { relTime } from '../lib/utils';
import RoleTag from '../components/RoleTag';

interface ProjectCardProps {
  p: ProjectStatusRow;
  onClick: () => void;
}

export default function ProjectCard({ p, onClick }: ProjectCardProps) {
  const isBusy = p.status === 'busy';

  return (
    <div className={`proj-card ${isBusy ? 'busy' : ''}`} onClick={onClick}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className={`status-dot ${isBusy ? 'busy' : 'idle'}`}></span>
          <span style={{ fontWeight: 500, fontSize: 13 }}>{p.id}</span>
        </div>
        <span className="tag" style={{ color: isBusy ? 'var(--accent)' : 'var(--fg-4)' }}>
          {isBusy ? 'BUSY' : 'IDLE'}
        </span>
      </div>
      {isBusy && p.busyWorker ? (
        <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
          <RoleTag role={p.busyWorker.role} />
          <span className="mono" style={{ marginLeft: 6 }}>
            {p.busyWorker.model ?? p.busyWorker.role}
          </span>
        </div>
      ) : (
        <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
          last: <span className="mono">{p.lastEvent ?? '—'}</span>
          {' · '}
          {p.lastTs ? relTime(p.lastTs) + ' ago' : '—'}
        </div>
      )}
      <div style={{
        display: 'flex',
        alignItems: 'baseline',
        justifyContent: 'space-between',
        paddingTop: 8,
        borderTop: '1px solid var(--border)',
      }}>
        <span className="num" style={{ fontSize: 20, color: 'var(--fg)' }}>{p.points}</span>
        <span className="muted mono" style={{ fontSize: 10 }}>{p.totalEvents} ev / 24h</span>
      </div>
    </div>
  );
}
