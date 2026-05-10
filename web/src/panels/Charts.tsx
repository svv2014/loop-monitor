import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { fetchStatsActivity, fetchStatsStages, fetchStatsRework, fetchBoard } from '../lib/api';
import type { StatsActivity, StatsStage, StatsRework, BoardEntry } from '../lib/types';

// CSS variable values for recharts (can't use var() in SVG attrs directly)
const C = {
  accent:   'oklch(0.82 0.18 145)',
  dev:      'oklch(0.78 0.13 210)',
  qa:       'oklch(0.82 0.15 75)',
  reviewer: 'oklch(0.74 0.16 0)',
  merge:    'oklch(0.80 0.16 145)',
  po:       'oklch(0.74 0.16 295)',
  warn:     'oklch(0.82 0.16 80)',
  muted:    'oklch(0.42 0.008 250)',
  bg2:      'oklch(0.205 0.007 250)',
  border:   'oklch(0.275 0.008 250)',
  fg3:      'oklch(0.58 0.008 250)',
};

const STAGE_COLORS: Record<string, string> = {
  dev:    C.dev,
  review: C.reviewer,
  qa:     C.qa,
  merge:  C.merge,
  po:     C.po,
};

const TOOLTIP_STYLE = {
  background: C.bg2,
  border: `1px solid ${C.border}`,
  borderRadius: 2,
  fontSize: 11,
  fontFamily: 'var(--font-mono)',
  color: 'oklch(0.96 0.005 250)',
};

function aggregateActivityByDate(rows: StatsActivity[]): { date: string; n: number }[] {
  const map = new Map<string, number>();
  for (const r of rows) {
    map.set(r.date, (map.get(r.date) ?? 0) + r.n);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, n]) => ({ date: date.slice(5), n })); // MM-DD
}

function aggregatePointsByProject(entries: BoardEntry[]): { project: string; pts: number }[] {
  const map = new Map<string, number>();
  for (const e of entries) {
    map.set(e.project, (map.get(e.project) ?? 0) + e.total_points);
  }
  return [...map.entries()]
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10)
    .map(([project, pts]) => ({ project, pts }));
}

function stageToMinutes(rows: StatsStage[]): { stage: string; minutes: number }[] {
  return rows.map(r => ({
    stage: r.stage,
    minutes: Math.round(r.avg_seconds / 60),
  }));
}

function reworkRates(rows: StatsRework[]): { project: string; rate: number }[] {
  return rows
    .filter(r => r.review_dones > 0)
    .map(r => ({
      project: r.project,
      rate: Math.round((r.rework_starts / r.review_dones) * 100),
    }))
    .sort((a, b) => b.rate - a.rate)
    .slice(0, 10);
}

function ChartPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="panel">
      <div className="panel-h"><span>{title}</span></div>
      <div style={{ padding: 'var(--pad-2) var(--pad-3) var(--pad-3)' }}>
        {children}
      </div>
    </div>
  );
}

function LoadingOrError({ loading, error }: { loading: boolean; error: boolean }) {
  if (loading) return <div style={{ height: 220, display: 'flex', alignItems: 'center', color: C.fg3, fontSize: 11 }}>Loading…</div>;
  if (error)   return <div style={{ height: 220, display: 'flex', alignItems: 'center', color: C.fg3, fontSize: 11 }}>Failed to load</div>;
  return null;
}

export default function Charts() {
  const activityQ = useQuery({
    queryKey: ['stats-activity'],
    queryFn: fetchStatsActivity,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const boardQ = useQuery({
    queryKey: ['board'],
    queryFn: fetchBoard,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const stagesQ = useQuery({
    queryKey: ['stats-stages'],
    queryFn: fetchStatsStages,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const reworkQ = useQuery({
    queryKey: ['stats-rework'],
    queryFn: fetchStatsRework,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const activityData = aggregateActivityByDate(activityQ.data ?? []);
  const pointsData   = aggregatePointsByProject(boardQ.data ?? []);
  const stagesData   = stageToMinutes(stagesQ.data ?? []);
  const reworkData   = reworkRates(reworkQ.data ?? []);

  return (
    <div className="charts-grid">
      {/* Events/Day */}
      <ChartPanel title="Events / Day">
        {activityQ.isLoading || activityQ.isError ? (
          <LoadingOrError loading={activityQ.isLoading} error={activityQ.isError} />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={activityData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <XAxis dataKey="date" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'oklch(1 0 0 / 0.03)' }} />
              <Bar dataKey="n" name="Events" fill={C.accent} radius={[2, 2, 0, 0]} maxBarSize={24} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartPanel>

      {/* Total Points by Project */}
      <ChartPanel title="Total Points by Project">
        {boardQ.isLoading || boardQ.isError ? (
          <LoadingOrError loading={boardQ.isLoading} error={boardQ.isError} />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={pointsData} layout="vertical" margin={{ top: 0, right: 8, left: 4, bottom: 0 }}>
              <XAxis type="number" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="project" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} width={90} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'oklch(1 0 0 / 0.03)' }} />
              <Bar dataKey="pts" name="Points" fill={C.dev} radius={[0, 2, 2, 0]} maxBarSize={16} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartPanel>

      {/* Avg Minutes per Stage */}
      <ChartPanel title="Avg Minutes per Stage">
        {stagesQ.isLoading || stagesQ.isError ? (
          <LoadingOrError loading={stagesQ.isLoading} error={stagesQ.isError} />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stagesData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <XAxis dataKey="stage" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'oklch(1 0 0 / 0.03)' }} formatter={(v) => [`${v} min`, 'Avg']} />
              <Bar dataKey="minutes" name="Avg min" radius={[2, 2, 0, 0]} maxBarSize={40}>
                {stagesData.map((entry) => (
                  <Cell key={entry.stage} fill={STAGE_COLORS[entry.stage] ?? C.accent} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartPanel>

      {/* Rework Rate */}
      <ChartPanel title="Rework Rate">
        {reworkQ.isLoading || reworkQ.isError ? (
          <LoadingOrError loading={reworkQ.isLoading} error={reworkQ.isError} />
        ) : reworkData.length === 0 ? (
          <div style={{ height: 220, display: 'flex', alignItems: 'center', color: C.fg3, fontSize: 11 }}>No rework data</div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={reworkData} layout="vertical" margin={{ top: 0, right: 8, left: 4, bottom: 0 }}>
              <XAxis type="number" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} unit="%" />
              <YAxis type="category" dataKey="project" tick={{ fill: C.fg3, fontSize: 9 }} axisLine={false} tickLine={false} width={90} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'oklch(1 0 0 / 0.03)' }} formatter={(v) => [`${v}%`, 'Rework rate']} />
              <Bar dataKey="rate" name="Rework %" fill={C.warn} radius={[0, 2, 2, 0]} maxBarSize={16} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartPanel>
    </div>
  );
}
