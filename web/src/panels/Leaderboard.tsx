import { useState, useMemo } from 'react';
import type { LoopEvent } from '../lib/types';
import { buildLeaderboard } from '../lib/transforms';
import RoleTag from '../components/RoleTag';

interface LeaderboardProps {
  events: LoopEvent[];
}

export default function Leaderboard({ events }: LeaderboardProps) {
  const [by, setBy] = useState<'role' | 'agent'>('role');
  const rows = useMemo(
    () => buildLeaderboard(events as Parameters<typeof buildLeaderboard>[0], by).slice(0, 8),
    [events, by],
  );
  const maxPts = Math.max(1, ...rows.map(r => r.points));

  return (
    <div className="panel">
      <div className="panel-h">
        <span>Leaderboard</span>
        <span className="actions">
          <button className={`btn ${by === 'role' ? 'primary' : ''}`} onClick={() => setBy('role')}>
            by role
          </button>
          <button className={`btn ${by === 'agent' ? 'primary' : ''}`} onClick={() => setBy('agent')}>
            by agent
          </button>
        </span>
      </div>
      <table className="t">
        <thead>
          <tr>
            <th style={{ width: 30 }}>#</th>
            <th>{by === 'role' ? 'Role' : 'Agent'}</th>
            <th style={{ textAlign: 'right' }}>Verdicts</th>
            <th style={{ textAlign: 'right' }}>Points</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.key}>
              <td className="muted mono">{String(i + 1).padStart(2, '0')}</td>
              <td>
                {by === 'role'
                  ? <RoleTag role={r.key} />
                  : <span className="mono" style={{ fontSize: 12 }}>{r.key}</span>}
              </td>
              <td className="num muted" style={{ textAlign: 'right' }}>{r.verdicts}</td>
              <td style={{ textAlign: 'right', position: 'relative' }}>
                <div style={{
                  position: 'absolute', right: 0, top: 0, bottom: 0,
                  width: `${(r.points / maxPts) * 100}%`,
                  background: 'oklch(0.82 0.18 145 / 0.08)',
                  pointerEvents: 'none',
                }} />
                <span className="num" style={{ position: 'relative', color: 'var(--fg)' }}>
                  {r.points}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
