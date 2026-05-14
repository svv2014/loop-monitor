import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell,
} from 'recharts';
import { fetchAnalyticsQuality } from '../lib/api';
import type { AnalyticsQuality } from '../lib/types';

const C = {
  accent:       'oklch(0.82 0.18 145)',
  dev:          'oklch(0.78 0.13 210)',
  qa:           'oklch(0.82 0.15 75)',
  warn:         'oklch(0.82 0.16 80)',
  err:          'oklch(0.72 0.20 25)',
  muted:        'oklch(0.42 0.008 250)',
  bg2:          'oklch(0.205 0.007 250)',
  border:       'oklch(0.275 0.008 250)',
  fg3:          'oklch(0.58 0.008 250)',
  clean:        'oklch(0.72 0.18 145)',
  light_rework: 'oklch(0.82 0.15 75)',
  heavy_rework: 'oklch(0.80 0.20 55)',
  blocked:      'oklch(0.65 0.20 25)',
};

const TOOLTIP_STYLE = {
  background: C.bg2,
  border: `1px solid ${C.border}`,
  borderRadius: 2,
  fontSize: 11,
  fontFamily: 'var(--font-mono)',
  color: 'oklch(0.96 0.005 250)',
};

function SubPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="panel">
      <div className="panel-h"><span>{title}</span></div>
      <div style={{ padding: 'var(--pad-2) var(--pad-3) var(--pad-3)' }}>{children}</div>
    </div>
  );
}

function Placeholder({ height = 180 }: { height?: number }) {
  return <div style={{ height, display: 'flex', alignItems: 'center', color: C.fg3, fontSize: 11 }}>Loading…</div>;
}

function VerdictDonut({ data }: { data: AnalyticsQuality['verdicts'] }) {
  const entries = [
    { name: 'Clean',        value: data.clean,        fill: C.clean },
    { name: 'Light rework', value: data.light_rework,  fill: C.light_rework },
    { name: 'Heavy rework', value: data.heavy_rework,  fill: C.heavy_rework },
    { name: 'Blocked',      value: data.blocked,       fill: C.blocked },
  ].filter(e => e.value > 0);

  const total = entries.reduce((s, e) => s + e.value, 0);
  if (total === 0) {
    return <div style={{ height: 180, display: 'flex', alignItems: 'center', color: C.fg3, fontSize: 11 }}>No verdicts yet</div>;
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--pad-3)' }}>
      <PieChart width={140} height={140}>
        <Pie data={entries} dataKey="value" cx={65} cy={65} innerRadius={38} outerRadius={60} strokeWidth={0}>
          {entries.map(e => <Cell key={e.name} fill={e.fill} />)}
        </Pie>
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => { const n = Number(v); return [`${n} (${((n / total) * 100).toFixed(0)}%)`, ''] as [string, string]; }} />
      </PieChart>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {entries.map(e => (
          <div key={e.name} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: e.fill, flexShrink: 0 }} />
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'oklch(0.96 0.005 250)' }}>
              {e.name}
            </span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: C.fg3, marginLeft: 4 }}>
              {e.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function QASparkline({ daily }: { daily: AnalyticsQuality['qa_pass_rate_daily'] }) {
  if (daily.length === 0) {
    return <div style={{ height: 140, display: 'flex', alignItems: 'center', color: C.fg3, fontSize: 11 }}>No QA data</div>;
  }
  const chartData = daily.map(d => ({ date: d.date.slice(5), rate: Math.round(d.rate * 100) }));
  return (
    <ResponsiveContainer width="100%" height={140}>
      <LineChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis dataKey="date" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 100]} tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} unit="%" />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v}%`, 'QA pass rate'] as [string, string]} />
        <Line type="monotone" dataKey="rate" stroke={C.accent} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function StageFailureChart({ data }: { data: AnalyticsQuality['stage_failure'] }) {
  const chartData = data.map(d => ({ stage: d.stage, pct: Math.round(d.fail_rate * 100), sample: d.sample }));
  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
        <XAxis type="number" domain={[0, 100]} tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} unit="%" />
        <YAxis type="category" dataKey="stage" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} width={48} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v, _n, p) => [`${v}% (n=${(p.payload as { sample: number }).sample})`, 'Fail rate'] as [string, string]} />
        <Bar dataKey="pct" name="Fail %" fill={C.warn} radius={[0, 2, 2, 0]} maxBarSize={14} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function ReworkHistogram({ data }: { data: AnalyticsQuality['rework_dist'] }) {
  return (
    <div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
        {(['p50', 'p75', 'p95'] as const).map(k => (
          <div key={k} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'oklch(0.96 0.005 250)' }}>
              {data[k].toFixed(1)}×
            </span>
            <span style={{ fontSize: 9, color: C.fg3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{k}</span>
          </div>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data.buckets} margin={{ top: 0, right: 4, left: -20, bottom: 0 }}>
          <XAxis dataKey="label" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [v, 'Issues'] as [typeof v, string]} />
          <Bar dataKey="count" name="Issues" fill={C.dev} radius={[2, 2, 0, 0]} maxBarSize={32} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function FailureTypesRow({ data }: { data: AnalyticsQuality['failure_types'] }) {
  const items: { label: string; value: number; color: string }[] = [
    { label: 'PO',     value: data.po_failed,     color: 'oklch(0.74 0.16 295)' },
    { label: 'Dev',    value: data.dev_failed,     color: C.dev },
    { label: 'QA',     value: data.qa_fail,        color: C.qa },
    { label: 'Review', value: data.review_failed,  color: 'oklch(0.74 0.16 0)' },
    { label: 'Merge',  value: data.merge_failed,   color: C.accent },
  ];
  return (
    <div style={{ display: 'flex', gap: 'var(--pad-3)', flexWrap: 'wrap' }}>
      {items.map(it => (
        <div key={it.label} style={{
          flex: '1 1 0',
          minWidth: 72,
          padding: 'var(--pad-2) var(--pad-3)',
          background: C.bg2,
          border: `1px solid ${C.border}`,
          borderRadius: 4,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2,
        }}>
          <span style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: it.color }}>
            {it.value}
          </span>
          <span style={{ fontSize: 9, color: C.fg3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            {it.label}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Quality() {
  const q = useQuery({
    queryKey: ['analytics-quality'],
    queryFn: () => fetchAnalyticsQuality(30),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const data = q.data;
  const loading = q.isLoading;

  return (
    <div style={{ display: 'grid', gap: 'var(--pad-3)', gridTemplateColumns: '1fr 1fr' }}>
      <SubPanel title="Verdict Mix">
        {loading || !data ? <Placeholder /> : <VerdictDonut data={data.verdicts} />}
      </SubPanel>

      <SubPanel title="QA Pass Rate (30d)">
        {loading || !data ? <Placeholder height={140} /> : (
          <div>
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontSize: 22, fontFamily: 'var(--font-mono)', fontWeight: 600, color: C.accent }}>
                {(data.qa_pass_rate * 100).toFixed(1)}%
              </span>
              <span style={{ fontSize: 9, color: C.fg3, marginLeft: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>overall</span>
            </div>
            <QASparkline daily={data.qa_pass_rate_daily} />
          </div>
        )}
      </SubPanel>

      <SubPanel title="Stage Failure Rate">
        {loading || !data ? <Placeholder height={160} /> : <StageFailureChart data={data.stage_failure} />}
      </SubPanel>

      <SubPanel title="Rework Factor Distribution">
        {loading || !data ? <Placeholder height={160} /> : <ReworkHistogram data={data.rework_dist} />}
      </SubPanel>

      <div style={{ gridColumn: '1 / -1' }}>
        <SubPanel title="Failures by Type">
          {loading || !data ? <Placeholder height={60} /> : <FailureTypesRow data={data.failure_types} />}
        </SubPanel>
      </div>
    </div>
  );
}
