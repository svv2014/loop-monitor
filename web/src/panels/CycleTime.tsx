import { useQuery } from '@tanstack/react-query';
import { fetchAnalyticsCycleTime } from '../lib/api';
import type { CycleTimeStage, CycleTimePct } from '../lib/types';

function fmtSecs(secs: number): string {
  if (secs < 60) return `${Math.round(secs)}s`;
  if (secs < 3600) return `${Math.round(secs / 60)}m`;
  if (secs < 86400) {
    const h = Math.floor(secs / 3600);
    const m = Math.round((secs % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  const d = Math.floor(secs / 86400);
  const h = Math.round((secs % 86400) / 3600);
  return h > 0 ? `${d}d ${h}h` : `${d}d`;
}

function StageRow({ row }: { row: CycleTimeStage }) {
  return (
    <tr>
      <td className="mono" style={{ fontSize: 11, color: 'var(--fg-2)' }}>{row.stage}</td>
      <td className="num">{fmtSecs(row.p50)}</td>
      <td className="num">{fmtSecs(row.p75)}</td>
      <td className="num">{fmtSecs(row.p95)}</td>
      <td className="num" style={{ color: 'var(--fg-3)', fontSize: 11 }}>{row.count}</td>
    </tr>
  );
}

function LeadTimeRow({ lt }: { lt: CycleTimePct }) {
  return (
    <tr style={{ borderTop: '1px solid var(--border)', fontWeight: 500 }}>
      <td className="mono" style={{ fontSize: 11 }}>lead-time (end-to-end)</td>
      <td className="num">{fmtSecs(lt.p50)}</td>
      <td className="num">{fmtSecs(lt.p75)}</td>
      <td className="num">{fmtSecs(lt.p95)}</td>
      <td className="num" style={{ color: 'var(--fg-3)', fontSize: 11 }}>{lt.count}</td>
    </tr>
  );
}

interface CycleTimePanelProps {
  days?: number;
}

export default function CycleTimePanel({ days = 30 }: CycleTimePanelProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['analytics-cycle-time', days],
    queryFn: () => fetchAnalyticsCycleTime(days),
    staleTime: 60_000,
    refetchInterval: 300_000,
  });

  return (
    <div className="panel" id="cycle-time">
      <div className="panel-h">
        <span>Cycle time · last {days}d</span>
        {data && (
          <span className="muted mono" style={{ fontSize: 10 }}>
            {data.stages.length} stages · {data.lead_time?.count ?? 0} full runs
          </span>
        )}
      </div>

      {isLoading && (
        <div className="muted" style={{ padding: 'var(--pad-3)' }}>Loading…</div>
      )}

      {isError && (
        <div style={{ padding: 'var(--pad-3)', color: 'var(--role-err)', fontSize: 12 }}>
          Failed to load cycle time data.
        </div>
      )}

      {data && (data.stages.length > 0 || data.lead_time != null) ? (
        <table className="t">
          <thead>
            <tr>
              <th>Stage</th>
              <th>p50</th>
              <th>p75</th>
              <th>p95</th>
              <th>n</th>
            </tr>
          </thead>
          <tbody>
            {data.stages.map(s => (
              <StageRow key={s.stage} row={s} />
            ))}
            {data.lead_time != null && <LeadTimeRow lt={data.lead_time} />}
          </tbody>
        </table>
      ) : (
        !isLoading && !isError && (
          <div className="muted" style={{ padding: 'var(--pad-3)', fontSize: 12 }}>
            No cycle time data in the last {days} days.
          </div>
        )
      )}
    </div>
  );
}
