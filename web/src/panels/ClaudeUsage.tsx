import { useQuery } from '@tanstack/react-query';
import { fetchClaudeUsage } from '../lib/api';

function fmtDur(seconds: number): string {
  if (seconds >= 86400) {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    return h > 0 ? `${d}d ${h}h` : `${d}d`;
  }
  if (seconds >= 3600) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function ClaudeUsage() {
  const { data, isError } = useQuery({
    queryKey: ['claude-usage'],
    queryFn: fetchClaudeUsage,
    refetchInterval: (query) => {
      const d = query.state.data;
      return ((d?.refresh_seconds ?? 300) * 1000);
    },
    staleTime: 60_000,
  });

  if (!data || !data.enabled || isError) return null;

  if (data.error) {
    return (
      <div className="panel">
        <div className="panel-h"><span>Claude Usage</span></div>
        <div style={{ padding: 'var(--pad-3)', fontSize: '0.82rem', color: 'var(--fg-3)' }}>
          Claude usage unavailable: {data.error}
        </div>
      </div>
    );
  }

  const pct = Math.min(100, Math.max(0, data.quota_pct ?? 0));
  const fillClass = pct >= 90 ? 'usage-fill usage-critical' : pct >= 75 ? 'usage-fill usage-warn' : 'usage-fill';

  const resetSecs = data.reset_at
    ? Math.max(0, Math.floor((new Date(data.reset_at).getTime() - Date.now()) / 1000))
    : null;
  const resetStr = resetSecs != null ? `resets in ${fmtDur(resetSecs)}` : '';

  const usedStr = data.quota_used != null ? data.quota_used.toLocaleString() : '?';
  const limitStr = data.quota_limit != null ? data.quota_limit.toLocaleString() : '?';

  return (
    <div className="panel">
      <div className="panel-h"><span>Claude Usage</span></div>
      <div style={{ padding: 'var(--pad-3)' }}>
        <div className="usage-bar">
          <div className={fillClass} style={{ width: `${pct}%` }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--fg-3)' }}>
          <span>{usedStr} / {limitStr} &middot; {pct}%</span>
          {resetStr && <span>{resetStr}</span>}
        </div>
      </div>
    </div>
  );
}
