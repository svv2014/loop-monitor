import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, ReferenceLine,
} from 'recharts';
import { fetchAnalyticsQuality } from '../lib/api';
import type {
  QualityAnalyticsResponse,
  QualityStageFailure,
  QualityDailyRate,
  QualityReworkBucket,
} from '../lib/types';

const C = {
  clean:       'oklch(0.72 0.17 145)',
  light:       'oklch(0.82 0.16 80)',
  heavy:       'oklch(0.78 0.17 40)',
  blocked:     'oklch(0.62 0.22 20)',
  accent:      'oklch(0.82 0.18 145)',
  qa:          'oklch(0.82 0.15 75)',
  warn:        'oklch(0.82 0.16 80)',
  err:         'oklch(0.62 0.22 20)',
  fg3:         'oklch(0.58 0.008 250)',
  bg2:         'oklch(0.205 0.007 250)',
  border:      'oklch(0.275 0.008 250)',
};

const TOOLTIP_STYLE = {
  background: C.bg2,
  border: `1px solid ${C.border}`,
  borderRadius: 2,
  fontSize: 11,
  fontFamily: 'var(--font-mono)',
  color: 'oklch(0.96 0.005 250)',
};

const VERDICT_COLORS = [C.clean, C.light, C.heavy, C.blocked];

function pct(n: number, total: number): string {
  return total === 0 ? '0%' : `${Math.round((n / total) * 100)}%`;
}

function VerdictBar({ data }: { data: QualityAnalyticsResponse['verdicts'] }) {
  const total = data.clean + data.light_rework + data.heavy_rework + data.blocked;
  const segments = [
    { key: 'clean',        label: 'clean',       value: data.clean,        color: C.clean },
    { key: 'light_rework', label: 'light rework', value: data.light_rework, color: C.light },
    { key: 'heavy_rework', label: 'heavy rework', value: data.heavy_rework, color: C.heavy },
    { key: 'blocked',      label: 'blocked',      value: data.blocked,      color: C.blocked },
  ];

  return (
    <div>
      <div style={{ display: 'flex', height: 10, borderRadius: 2, overflow: 'hidden', gap: 1 }}>
        {segments.map(s => (
          <div
            key={s.key}
            style={{
              flex: s.value,
              background: s.color,
              minWidth: s.value > 0 ? 2 : 0,
            }}
          />
        ))}
        {total === 0 && <div style={{ flex: 1, background: C.border }} />}
      </div>
      <div style={{ display: 'flex', gap: 'var(--pad-3)', marginTop: 6, flexWrap: 'wrap' }}>
        {segments.map(s => (
          <span key={s.key} style={{ fontSize: 11, color: C.fg3, display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 1, background: s.color }} />
            {s.label}
            <span style={{ color: s.color, fontFamily: 'var(--font-mono)' }}>
              {s.value} <span style={{ color: C.fg3 }}>({pct(s.value, total)})</span>
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

function QaSparkline({ daily }: { daily: QualityDailyRate[] }) {
  const chartData = daily.map(d => ({ date: d.date.slice(5), rate: d.rate != null ? Math.round(d.rate * 100) : null }));
  return (
    <ResponsiveContainer width="100%" height={60}>
      <LineChart data={chartData} margin={{ top: 4, right: 4, left: -32, bottom: 0 }}>
        <XAxis dataKey="date" tick={false} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 100]} tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(v) => [`${v}%`, 'QA pass']}
          labelFormatter={(l) => l}
        />
        <ReferenceLine y={80} stroke={C.border} strokeDasharray="3 3" />
        <Line
          type="monotone"
          dataKey="rate"
          stroke={C.qa}
          dot={false}
          strokeWidth={1.5}
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function StageFailureChart({ rows }: { rows: QualityStageFailure[] }) {
  const data = rows.map(r => ({
    stage: r.stage,
    fail_pct: Math.round(r.fail_rate * 100),
    sample: r.sample,
  }));
  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis dataKey="stage" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(v, _name, props) => [
            `${v}% (n=${(props.payload as { sample?: number })?.sample ?? 0})`,
            'fail rate',
          ]}
        />
        <Bar dataKey="fail_pct" name="fail rate" radius={[2, 2, 0, 0]} maxBarSize={40}>
          {data.map(d => (
            <Cell
              key={d.stage}
              fill={d.fail_pct > 30 ? C.err : d.fail_pct > 10 ? C.warn : C.accent}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ReworkHistogram({ buckets }: { buckets: QualityReworkBucket[] }) {
  return (
    <ResponsiveContainer width="100%" height={100}>
      <BarChart data={buckets} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis dataKey="label" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [v, 'issues']} />
        <Bar dataKey="count" name="issues" radius={[2, 2, 0, 0]} maxBarSize={40}>
          {buckets.map((b, i) => (
            <Cell key={b.label} fill={VERDICT_COLORS[i] ?? C.accent} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

interface QualityPanelProps {
  days?: number;
}

export default function QualityPanel({ days = 30 }: QualityPanelProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['analytics-quality', days],
    queryFn: () => fetchAnalyticsQuality(days),
    staleTime: 60_000,
    refetchInterval: 300_000,
  });

  return (
    <div className="panel" id="quality">
      <div className="panel-h">
        <span>Quality · last {days}d</span>
        {data && (
          <span className="muted mono" style={{ fontSize: 10 }}>
            {data.verdicts.clean + data.verdicts.light_rework + data.verdicts.heavy_rework + data.verdicts.blocked} issues
            {data.qa_pass_rate != null && ` · QA ${Math.round(data.qa_pass_rate * 100)}%`}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="muted" style={{ padding: 'var(--pad-3)' }}>Loading…</div>
      )}

      {isError && (
        <div style={{ padding: 'var(--pad-3)', color: 'var(--role-err)', fontSize: 12 }}>
          Failed to load quality data.
        </div>
      )}

      {data && (
        <div style={{ padding: 'var(--pad-3)', display: 'grid', gap: 'var(--pad-3)' }}>

          {/* Verdict mix */}
          <div>
            <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>Verdict mix</div>
            <VerdictBar data={data.verdicts} />
          </div>

          {/* QA pass rate */}
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
              <span className="muted" style={{ fontSize: 11 }}>QA pass rate</span>
              {data.qa_pass_rate != null ? (
                <span style={{ fontSize: 14, fontWeight: 600, fontFamily: 'var(--font-mono)', color: data.qa_pass_rate >= 0.8 ? C.clean : data.qa_pass_rate >= 0.5 ? C.warn : C.err }}>
                  {Math.round(data.qa_pass_rate * 100)}%
                </span>
              ) : (
                <span className="muted" style={{ fontSize: 12 }}>—</span>
              )}
            </div>
            {data.qa_pass_rate_daily.some(d => d.rate != null) && (
              <QaSparkline daily={data.qa_pass_rate_daily} />
            )}
          </div>

          {/* Stage failure */}
          {data.stage_failure.length > 0 && (
            <div>
              <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>Stage failure rate</div>
              <StageFailureChart rows={data.stage_failure} />
            </div>
          )}

          {/* Rework factor distribution */}
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
              <span className="muted" style={{ fontSize: 11 }}>Rework factor</span>
              {data.rework_dist.p50 != null && (
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: C.fg3 }}>
                  p50 {data.rework_dist.p50.toFixed(2)}x · p75 {data.rework_dist.p75?.toFixed(2)}x · p95 {data.rework_dist.p95?.toFixed(2)}x
                </span>
              )}
            </div>
            <ReworkHistogram buckets={data.rework_dist.buckets} />
          </div>

          {/* Failure types */}
          <div>
            <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>Failure counts</div>
            <div style={{ display: 'flex', gap: 'var(--pad-3)', flexWrap: 'wrap' }}>
              {(
                [
                  ['PO',     data.failure_types.po_failed],
                  ['Dev',    data.failure_types.dev_failed],
                  ['QA',     data.failure_types.qa_fail],
                  ['Review', data.failure_types.review_failed],
                  ['Merge',  data.failure_types.merge_failed],
                ] as [string, number][]
              ).map(([label, count]) => (
                <div key={label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 600, fontFamily: 'var(--font-mono)', color: count > 0 ? C.warn : C.fg3 }}>
                    {count}
                  </div>
                  <div style={{ fontSize: 10, color: C.fg3 }}>{label} fail</div>
                </div>
              ))}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
