import { useQuery } from '@tanstack/react-query';

// ── Types ─────────────────────────────────────────────────────────────────────

interface DailyBucket {
  date: string;
  count: number;
}

interface PerProjectVelocity {
  slug: string;
  today: number;
  avg_per_day: number;
}

interface VelocityResponse {
  today: number;
  avg_per_day: number;
  prev_period_avg: number;
  trend_pct: number;
  daily: DailyBucket[];
  per_project: PerProjectVelocity[];
}

// ── API fetch ─────────────────────────────────────────────────────────────────

async function fetchVelocity(days = 30, project?: string): Promise<VelocityResponse> {
  const p = new URLSearchParams({ days: String(days) });
  if (project) p.set('project', project);
  const res = await fetch(`/api/analytics/velocity?${p.toString()}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<VelocityResponse>;
}

// ── Sparkline (inline SVG — no dependency) ────────────────────────────────────

function Sparkline({ data }: { data: DailyBucket[] }) {
  if (data.length < 2) return null;

  const counts = data.map(d => d.count);
  const max = Math.max(1, ...counts);
  const W = 200;
  const H = 36;
  const step = W / (counts.length - 1);

  const points = counts
    .map((c, i) => `${i * step},${H - (c / max) * (H - 4)}`)
    .join(' ');

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      aria-hidden="true"
      style={{ display: 'block', overflow: 'visible' }}
    >
      <polyline
        points={points}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

// ── Big-number KPI cell ───────────────────────────────────────────────────────

function KpiCell({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
}) {
  return (
    <div style={{ flex: 1, padding: 'var(--pad-3) var(--pad-4)', borderRight: '1px solid var(--border)' }}>
      <div
        style={{
          fontSize: 10,
          fontFamily: 'var(--font-mono)',
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          color: 'var(--fg-3)',
          marginBottom: 'var(--pad-1)',
        }}
      >
        {label}
      </div>
      <div
        className="num"
        style={{
          fontSize: 24,
          fontFamily: 'var(--font-mono)',
          fontVariantNumeric: 'tabular-nums',
          color: 'var(--fg)',
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      {sub != null && (
        <div
          style={{
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
            color: 'var(--fg-3)',
            marginTop: 'var(--pad-1)',
          }}
        >
          {sub}
        </div>
      )}
    </div>
  );
}

// ── Trend arrow + percentage ──────────────────────────────────────────────────

function TrendBadge({ pct }: { pct: number }) {
  if (pct === 0) {
    return <span style={{ color: 'var(--fg-3)' }}>— 0%</span>;
  }
  const up = pct > 0;
  return (
    <span style={{ color: up ? 'var(--pass)' : 'var(--fail)' }}>
      {up ? '▲' : '▼'} {Math.abs(pct)}%
    </span>
  );
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface VelocityProps {
  days?: number;
  project?: string;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function Velocity({ days = 30, project }: VelocityProps) {
  const { data, isLoading, isError } = useQuery<VelocityResponse>({
    queryKey: ['analytics-velocity', days, project ?? ''],
    queryFn: () => fetchVelocity(days, project),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  return (
    <div className="panel">
      <div className="panel-h">
        <span>Merge velocity</span>
        {project && (
          <span className="muted" style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>
            {project}
          </span>
        )}
      </div>

      {isLoading && (
        <div
          style={{
            padding: 'var(--pad-4)',
            color: 'var(--fg-3)',
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
          }}
        >
          Loading…
        </div>
      )}

      {isError && (
        <div
          style={{
            padding: 'var(--pad-4)',
            color: 'var(--fail)',
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
          }}
        >
          Failed to load velocity data
        </div>
      )}

      {data && (
        <>
          {/* KPI strip */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
            <KpiCell label="Today" value={data.today} />
            <KpiCell
              label="7-Day Avg"
              value={(data.avg_per_day).toFixed(1)}
              sub={`prev ${data.prev_period_avg.toFixed(1)}/day`}
            />
            <KpiCell
              label="30-Day Trend"
              value={<TrendBadge pct={data.trend_pct} />}
              sub="vs prior 7 days"
            />
          </div>

          {/* Sparkline */}
          {data.daily.length > 1 && (
            <div
              style={{
                padding: 'var(--pad-3) var(--pad-4)',
                borderBottom: data.per_project.length > 0 ? '1px solid var(--border)' : undefined,
              }}
            >
              <Sparkline data={data.daily} />
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginTop: 'var(--pad-1)',
                  fontSize: 9,
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--fg-4)',
                }}
              >
                <span>{data.daily[0]?.date?.slice(5)}</span>
                <span>{data.daily[data.daily.length - 1]?.date?.slice(5)}</span>
              </div>
            </div>
          )}

          {/* Per-project table */}
          {data.per_project.length > 0 && (
            <table className="t" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>Project</th>
                  <th style={{ textAlign: 'right' }}>Today</th>
                  <th style={{ textAlign: 'right' }}>Avg/day</th>
                </tr>
              </thead>
              <tbody>
                {data.per_project.map(p => (
                  <tr key={p.slug}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{p.slug}</td>
                    <td className="num" style={{ textAlign: 'right' }}>{p.today}</td>
                    <td className="num" style={{ textAlign: 'right' }}>{p.avg_per_day.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
