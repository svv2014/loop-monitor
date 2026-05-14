import type { CostTrend, CostTrendBucket } from '../lib/types';

interface CostTrendStripProps {
  today: CostTrend['today'];
  vs_7d: number | null;
  vs_30d: number | null;
  buckets: CostTrendBucket[];
}

function reworkColor(v: number): string {
  if (v <= 1.0) return 'var(--role-ok)';
  if (v < 2.0)  return 'var(--fg-2)';
  if (v < 4.0)  return 'var(--role-warn)';
  return 'var(--role-err)';
}

/**
 * Color for a delta value (negative = improving = green, positive = degrading = red,
 * within ±5% relative to a baseline is treated as gray/stable).
 */
function deltaColor(delta: number | null, baseline: number | null): string {
  if (delta == null) return 'var(--fg-3)';
  const threshold = baseline != null && baseline !== 0 ? Math.abs(baseline) * 0.05 : 0.05;
  if (Math.abs(delta) <= threshold) return 'var(--fg-3)';
  return delta < 0 ? 'var(--pass)' : 'var(--fail)';
}

function formatDelta(delta: number | null): string {
  if (delta == null) return '—';
  const sign = delta > 0 ? '+' : '';
  return `${sign}${delta.toFixed(2)}`;
}

interface SparklineProps {
  buckets: CostTrendBucket[];
  width?: number;
  height?: number;
}

function Sparkline({ buckets, width = 120, height = 32 }: SparklineProps) {
  const withData = buckets.filter(b => b.median_rework_factor != null);
  if (withData.length < 2) {
    return (
      <svg
        width={width}
        height={height}
        aria-label="Sparkline — not enough data"
        style={{ display: 'block', flexShrink: 0 }}
      >
        <line
          x1={0} y1={height / 2}
          x2={width} y2={height / 2}
          stroke="var(--border)"
          strokeWidth={1}
          strokeDasharray="2 3"
        />
      </svg>
    );
  }

  const values = withData.map(b => b.median_rework_factor as number);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  const pad = 2;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;

  const toX = (i: number) => pad + (i / (withData.length - 1)) * innerW;
  const toY = (v: number) => pad + innerH - ((v - minVal) / range) * innerH;

  const points = withData.map((b, i) => `${toX(i)},${toY(b.median_rework_factor as number)}`).join(' ');

  const minIdx = values.indexOf(minVal);
  const maxIdx = values.indexOf(maxVal);

  return (
    <svg
      width={width}
      height={height}
      aria-label="30-day median rework factor sparkline"
      style={{ display: 'block', flexShrink: 0, overflow: 'visible' }}
    >
      <polyline
        points={points}
        fill="none"
        stroke="var(--fg-3)"
        strokeWidth={1}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {withData.map((b, i) => {
        const isMin = i === minIdx;
        const isMax = i === maxIdx;
        if (!isMin && !isMax) return null;
        const cx = toX(i);
        const cy = toY(b.median_rework_factor as number);
        const dotColor = isMax ? 'var(--fail)' : 'var(--pass)';
        return (
          <circle key={b.date} cx={cx} cy={cy} r={2.5} fill={dotColor}>
            <title>{`${b.date}: ${(b.median_rework_factor as number).toFixed(2)}`}</title>
          </circle>
        );
      })}
    </svg>
  );
}

export default function CostTrendStrip({ today, vs_7d, vs_30d, buckets }: CostTrendStripProps) {
  const med = today.median_rework_factor;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--pad-4)',
        padding: 'var(--pad-3) var(--pad-4)',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-1)',
        flexWrap: 'wrap',
      }}
    >
      {/* Today's median */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 80 }}>
        <span
          className="muted mono"
          style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}
        >
          today median
        </span>
        <span
          className="num"
          style={{
            fontSize: 28,
            fontFamily: 'var(--font-mono)',
            fontWeight: 600,
            color: med != null ? reworkColor(med) : 'var(--fg-3)',
            lineHeight: 1,
          }}
        >
          {med != null ? med.toFixed(2) : '—'}
        </span>
        {today.issue_count > 0 && (
          <span className="muted mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>
            {today.issue_count} issue{today.issue_count !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Separator */}
      <div style={{ width: 1, height: 40, background: 'var(--border)', flexShrink: 0 }} />

      {/* Deltas */}
      <div style={{ display: 'flex', gap: 'var(--pad-3)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span
            className="muted mono"
            style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}
          >
            vs 7d
          </span>
          <span
            className="num"
            style={{
              fontSize: 16,
              fontFamily: 'var(--font-mono)',
              fontWeight: 500,
              color: deltaColor(vs_7d, med),
            }}
          >
            {formatDelta(vs_7d)}
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span
            className="muted mono"
            style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}
          >
            vs 30d
          </span>
          <span
            className="num"
            style={{
              fontSize: 16,
              fontFamily: 'var(--font-mono)',
              fontWeight: 500,
              color: deltaColor(vs_30d, med),
            }}
          >
            {formatDelta(vs_30d)}
          </span>
        </div>
      </div>

      {/* Separator */}
      <div style={{ width: 1, height: 40, background: 'var(--border)', flexShrink: 0 }} />

      {/* Sparkline */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span
          className="muted mono"
          style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}
        >
          30d trend
        </span>
        <Sparkline buckets={buckets} width={120} height={32} />
      </div>
    </div>
  );
}
