import { useQuery } from '@tanstack/react-query';
import { fetchActive } from '../lib/api';

export function TopBar() {
  const query = useQuery({
    queryKey: ['active'],
    queryFn: () => fetchActive(),
    refetchInterval: 5000,
    staleTime: 0,
  });

  const workerCount = query.data?.length ?? 0;
  const connected = !query.isError;

  return (
    <header style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.5rem 1rem', borderBottom: '1px solid #333' }}>
      <span style={{ fontWeight: 600 }}>Loop Monitor</span>
      <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span>{workerCount} active</span>
        <span
          title={connected ? 'Connected' : 'Connection error'}
          style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: connected ? '#22c55e' : '#ef4444',
            display: 'inline-block',
          }}
        />
      </span>
    </header>
  );
}
