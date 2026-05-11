import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';
import { fetchTokenSpend } from '../lib/api';
import type { TokenSpendProject } from '../lib/types';

const ROLES = ['po', 'dev', 'qa', 'reviewer', 'merge', 'judge'] as const;

// Must match tokens.css --role-* values (CSS vars can't be used in SVG attrs)
const ROLE_COLOR: Record<string, string> = {
  po:       'oklch(0.74 0.16 295)',
  dev:      'oklch(0.78 0.13 210)',
  qa:       'oklch(0.82 0.15 75)',
  reviewer: 'oklch(0.74 0.16 0)',
  merge:    'oklch(0.80 0.16 145)',
  judge:    'oklch(0.74 0.14 260)',
};

const C = {
  bg2:    'oklch(0.205 0.007 250)',
  border: 'oklch(0.275 0.008 250)',
};

const TOOLTIP_STYLE = {
  background: C.bg2,
  border: `1px solid ${C.border}`,
  borderRadius: 2,
  fontSize: 11,
  fontFamily: 'var(--font-mono)',
  color: 'oklch(0.96 0.005 250)',
};

function fmtUsd(v: number): string {
  if (v === 0) return '$0';
  if (v < 0.01) return '<$0.01';
  return `$${v.toFixed(2)}`;
}

function fmtTok(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

function ProjectTable({ projects }: { projects: TokenSpendProject[] }) {
  if (projects.length === 0) {
    return (
      <div style={{ padding: 'var(--pad-3)', fontSize: '0.82rem', color: 'var(--fg-3)' }}>
        No events in the last 30 days.
      </div>
    );
  }
  return (
    <table className="t" style={{ fontSize: 11 }}>
      <thead>
        <tr>
          <th>Project</th>
          <th style={{ textAlign: 'right' }}>Today</th>
          <th style={{ textAlign: 'right' }}>In/Out</th>
          <th style={{ textAlign: 'right' }}>This week</th>
          <th style={{ textAlign: 'right' }}>In/Out</th>
          <th style={{ textAlign: 'right' }}>This month</th>
          <th style={{ textAlign: 'right' }}>In/Out</th>
        </tr>
      </thead>
      <tbody>
        {projects.map(row => (
          <tr key={row.project}>
            <td className="mono" style={{ fontSize: 10 }}>{row.project}</td>
            <td className="num" style={{ textAlign: 'right' }}>{fmtUsd(row.today_cost_usd)}</td>
            <td className="num" style={{ textAlign: 'right', color: 'var(--fg-3)', fontSize: 10 }}>
              {fmtTok(row.today_input_tokens)}/{fmtTok(row.today_output_tokens)}
            </td>
            <td className="num" style={{ textAlign: 'right' }}>{fmtUsd(row.week_cost_usd)}</td>
            <td className="num" style={{ textAlign: 'right', color: 'var(--fg-3)', fontSize: 10 }}>
              {fmtTok(row.week_input_tokens)}/{fmtTok(row.week_output_tokens)}
            </td>
            <td className="num" style={{ textAlign: 'right' }}>{fmtUsd(row.month_cost_usd)}</td>
            <td className="num" style={{ textAlign: 'right', color: 'var(--fg-3)', fontSize: 10 }}>
              {fmtTok(row.month_input_tokens)}/{fmtTok(row.month_output_tokens)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function TokenSpend() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ['token-spend'],
    queryFn: fetchTokenSpend,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="panel">
        <div className="panel-h"><span>Token Spend (est.)</span></div>
        <div style={{ padding: 'var(--pad-3)', fontSize: '0.82rem', color: 'var(--fg-3)' }}>Loading…</div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="panel">
        <div className="panel-h"><span>Token Spend (est.)</span></div>
        <div style={{ padding: 'var(--pad-3)', fontSize: '0.82rem', color: 'var(--fg-3)' }}>Unavailable</div>
      </div>
    );
  }

  const { chart, projects, config } = data;

  const configNote = `$${config.cost_per_1m_input}/$${config.cost_per_1m_output} per 1M in/out · ${fmtTok(config.est_input_per_event)}/${fmtTok(config.est_output_per_event)} tok/event (est.)`;

  return (
    <div className="panel">
      <div className="panel-h">
        <span>Token Spend (est.) — 7d by role</span>
        <span className="muted" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {ROLES.map(r => (
            <span key={r} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 8, height: 8, background: ROLE_COLOR[r], display: 'inline-block' }} />
              {r}
            </span>
          ))}
        </span>
      </div>

      <div style={{ height: 160, padding: 'var(--pad-3) var(--pad-3) 0' }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chart} barCategoryGap="20%" margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
            <XAxis
              dataKey="label"
              tick={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'oklch(0.42 0.008 250)' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'oklch(0.42 0.008 250)' }}
              tickFormatter={(v: number) => v === 0 ? '' : `$${v.toFixed(2)}`}
              axisLine={false}
              tickLine={false}
              width={40}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(value, name) => [typeof value === 'number' ? fmtUsd(value) : String(value), String(name)]}
              cursor={{ fill: 'oklch(1 0 0 / 0.03)' }}
            />
            {ROLES.map(role => (
              <Bar key={role} dataKey={role} stackId="s" fill={ROLE_COLOR[role]} radius={0} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', marginTop: 'var(--pad-2)' }}>
        <div style={{ padding: 'var(--pad-2) var(--pad-3)', fontSize: 9, color: 'var(--fg-4)', fontFamily: 'var(--font-mono)' }}>
          {configNote}
        </div>
        <ProjectTable projects={projects} />
      </div>
    </div>
  );
}
