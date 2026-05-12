import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { fetchTokenSpend } from '../lib/api';
import type { TokenSpendRow } from '../lib/types';

const C = {
  po:       'oklch(0.74 0.16 295)',
  dev:      'oklch(0.78 0.13 210)',
  qa:       'oklch(0.82 0.15 75)',
  reviewer: 'oklch(0.74 0.16 0)',
  merge:    'oklch(0.80 0.16 145)',
  judge:    'oklch(0.80 0.12 40)',
  fg3:      'oklch(0.58 0.008 250)',
  bg2:      'oklch(0.205 0.007 250)',
  border:   'oklch(0.275 0.008 250)',
} as const;

const ROLES = ['po', 'dev', 'qa', 'reviewer', 'merge', 'judge'] as const;

const TOOLTIP_STYLE = {
  background: C.bg2,
  border: `1px solid ${C.border}`,
  borderRadius: 2,
  fontSize: 11,
  fontFamily: 'var(--font-mono)',
  color: 'oklch(0.96 0.005 250)',
};

function fmtCost(v: number): string {
  if (v === 0) return '$0';
  if (v < 0.001) return `$${v.toFixed(5)}`;
  if (v < 1) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

function buildChartData(rows: TokenSpendRow[], sevenDaysAgo: string) {
  const map = new Map<string, Record<string, number>>();
  for (const row of rows) {
    if (row.date < sevenDaysAgo) continue;
    if (!map.has(row.date)) map.set(row.date, {});
    const d = map.get(row.date)!;
    d[row.role] = (d[row.role] ?? 0) + row.cost_usd;
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, roles]) => ({ date: date.slice(5), ...roles }));
}

function buildProjectTable(rows: TokenSpendRow[], today: string, weekAgo: string, monthAgo: string) {
  const map = new Map<string, { today: number; week: number; month: number; inp: number; out: number }>();
  for (const row of rows) {
    if (!map.has(row.project)) {
      map.set(row.project, { today: 0, week: 0, month: 0, inp: 0, out: 0 });
    }
    const p = map.get(row.project)!;
    if (row.date === today) p.today += row.cost_usd;
    if (row.date >= weekAgo) p.week += row.cost_usd;
    if (row.date >= monthAgo) p.month += row.cost_usd;
    p.inp += row.input_tokens;
    p.out += row.output_tokens;
  }
  return [...map.entries()]
    .map(([project, v]) => ({ project, ...v }))
    .sort((a, b) => b.month - a.month);
}

export default function TokenSpend() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['token-spend'],
    queryFn: fetchTokenSpend,
    refetchInterval: 300_000,
    staleTime: 60_000,
  });

  if (isLoading || isError || !data || data.rows.length === 0) return null;

  const today = new Date().toISOString().slice(0, 10);
  const sevenDaysAgo = new Date(Date.now() - 6 * 86_400_000).toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 29 * 86_400_000).toISOString().slice(0, 10);

  const chartData = buildChartData(data.rows, sevenDaysAgo);
  const projectRows = buildProjectTable(data.rows, today, sevenDaysAgo, monthAgo);

  const cfg = data.config;

  return (
    <div className="panel">
      <div className="panel-h"><span>Token Spend</span></div>
      <div style={{ padding: 'var(--pad-2) var(--pad-3) var(--pad-3)' }}>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
            <XAxis dataKey="date" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
            <YAxis
              tick={{ fill: C.fg3, fontSize: 9 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `$${v.toFixed(2)}`}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              cursor={{ fill: 'oklch(1 0 0 / 0.03)' }}
              formatter={(v, name) => [typeof v === 'number' ? fmtCost(v) : String(v), String(name)]}
            />
            <Legend iconSize={8} wrapperStyle={{ fontSize: 9, color: C.fg3 }} />
            {ROLES.map(role => (
              <Bar
                key={role}
                dataKey={role}
                stackId="a"
                fill={C[role]}
                name={role}
                maxBarSize={32}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>

        <table className="t" style={{ marginTop: 'var(--pad-3)', fontSize: 11 }}>
          <thead>
            <tr>
              <th>Project</th>
              <th>Today</th>
              <th>7 d</th>
              <th>30 d</th>
              <th>Input tkn</th>
              <th>Output tkn</th>
            </tr>
          </thead>
          <tbody>
            {projectRows.map(r => (
              <tr key={r.project}>
                <td className="mono" style={{ fontSize: 10 }}>{r.project}</td>
                <td className="num">{fmtCost(r.today)}</td>
                <td className="num">{fmtCost(r.week)}</td>
                <td className="num">{fmtCost(r.month)}</td>
                <td className="num mono" style={{ fontSize: 10, color: C.fg3 }}>{fmtTokens(r.inp)}</td>
                <td className="num mono" style={{ fontSize: 10, color: C.fg3 }}>{fmtTokens(r.out)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ marginTop: 'var(--pad-2)', fontSize: 10, color: C.fg3 }}>
          Estimated · {cfg.tokens_per_event.toLocaleString()} tokens/event
          · ${cfg.cost_per_1m_input}/1M in · ${cfg.cost_per_1m_output}/1M out
          · configure via <span className="mono">LOOPMON_TOKENS_PER_EVENT</span>,{' '}
          <span className="mono">LOOPMON_COST_PER_1M_INPUT</span>,{' '}
          <span className="mono">LOOPMON_COST_PER_1M_OUTPUT</span>
        </div>
      </div>
    </div>
  );
}
