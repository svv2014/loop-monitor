import { useQuery } from '@tanstack/react-query';
import { fetchHealth } from '../lib/api';

interface TopBarProps {
  loopId: string;
  onLoopChange: (id: string) => void;
}

export function TopBar({ loopId, onLoopChange }: TopBarProps) {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    staleTime: 0,
  });

  const version = health.data?.monitor_version ?? '…';
  const gitSha = health.data?.git_sha ?? '';
  const rawLoops = health.data?.loop_ids ?? [];
  const loops = rawLoops.filter(id => id !== '(unknown)');
  const connected = !health.isError;

  return (
    <header style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.5rem 1rem', borderBottom: '1px solid #333' }}>
      <span style={{ fontWeight: 600 }}>Loop Monitor</span>
      <span style={{ fontSize: '0.75rem', color: '#888' }}>
        v{version}
        {gitSha && <span style={{ marginLeft: 4, fontFamily: 'monospace' }}>({gitSha})</span>}
      </span>
      {loops.length > 1 && (
        <select
          value={loopId}
          onChange={e => onLoopChange(e.target.value)}
          style={{ marginLeft: 8, fontSize: '0.85rem', background: '#1a1a1a', color: '#eee', border: '1px solid #444', borderRadius: 4, padding: '2px 6px' }}
        >
          <option value="">All loops</option>
          {loops.map(id => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
      )}
      <span
        title={connected ? 'Connected' : 'Connection error'}
        style={{
          marginLeft: 'auto',
          width: 10,
          height: 10,
          borderRadius: '50%',
          background: connected ? '#22c55e' : '#ef4444',
          display: 'inline-block',
          flexShrink: 0,
        }}
      />
    </header>
  );
}
