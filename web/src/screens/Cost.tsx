import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchIssuesCost, fetchCostTrend } from '../lib/api';
import type { IssueCostRow } from '../lib/types';
import CostTrendStrip from '../components/CostTrendStrip';

const LIMIT = 50;

const TOOLTIP = 'rework_factor = actual_runs / happy_path_runs. happy_path_runs = 5 (po + dev + review + qa + merge), +5 per linked child issue. ≤1.0 = on budget, ≥2.0 = expensive, ≥4.0 = pathological.';

function reworkColor(v: number): string {
  if (v <= 1.0) return 'var(--role-ok)';
  if (v < 2.0)  return 'var(--fg-2)';
  if (v < 4.0)  return 'var(--role-warn)';
  return 'var(--role-err)';
}

function formatStranded(secs: number | null): string {
  if (secs == null || secs <= 0) return '—';
  if (secs < 60)    return '<1m';
  if (secs < 3600)  return `${Math.floor(secs / 60)}m`;
  if (secs < 86400) {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    return `${h}h ${m}m`;
  }
  const d = Math.floor(secs / 86400);
  const h = Math.floor((secs % 86400) / 3600);
  return `${d}d ${h}h`;
}

function formatLastEvent(iso: string | null): string {
  if (!iso) return '—';
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60)    return `${secs}s ago`;
  if (secs < 3600)  return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

function median(rows: IssueCostRow[]): number | null {
  if (rows.length === 0) return null;
  const sorted = [...rows].sort((a, b) => a.rework_factor - b.rework_factor);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1].rework_factor + sorted[mid].rework_factor) / 2
    : sorted[mid].rework_factor;
}

interface CostProps {
  globalProjectFilter?: string | null;
}

export default function Cost({ globalProjectFilter }: CostProps) {
  const [offset, setOffset] = useState(0);
  const [allRows, setAllRows] = useState<IssueCostRow[]>([]);
  const [filterProject, setFilterProject] = useState(globalProjectFilter ?? '');
  const [filterPriority, setFilterPriority] = useState('');

  useEffect(() => {
    setFilterProject(globalProjectFilter ?? '');
  }, [globalProjectFilter]);

  const query = useQuery({
    queryKey: ['issues-cost', offset],
    queryFn: async () => {
      const rows = await fetchIssuesCost({ limit: LIMIT, offset });
      setAllRows(prev => {
        const merged = offset === 0 ? rows : [...prev, ...rows];
        return merged;
      });
      return rows;
    },
    refetchInterval: 30_000,
    staleTime: 0,
  });

  const trendQuery = useQuery({
    queryKey: ['cost-trend', filterProject, filterPriority],
    queryFn: () => fetchCostTrend({
      days: 30,
      project: filterProject || undefined,
      priority: filterPriority || undefined,
    }),
    refetchInterval: 60_000,
    staleTime: 0,
  });

  const visible = allRows.filter(r => {
    if (filterProject && r.project !== filterProject) return false;
    if (filterPriority && r.priority !== filterPriority) return false;
    return true;
  });

  const projects = Array.from(new Set(allRows.map(r => r.project))).sort();
  const med = median(visible);
  const lastBatch = query.data ?? [];
  const hasMore = lastBatch.length >= LIMIT;

  return (
    <div>
      <div className="screen-h">
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--pad-3)' }}>
          <h1>Cost</h1>
          <span
            className="muted mono"
            style={{ fontSize: 11, cursor: 'help' }}
            title={TOOLTIP}
          >
            (?)
          </span>
        </div>
        {med != null && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <span
              className="num"
              style={{ fontSize: 28, fontFamily: 'var(--font-mono)', color: reworkColor(med), fontWeight: 600 }}
            >
              {med.toFixed(2)}
            </span>
            <span className="muted mono" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              median rework factor
            </span>
          </div>
        )}
      </div>

      {trendQuery.data && (
        <CostTrendStrip
          today={trendQuery.data.today}
          vs_7d={trendQuery.data.vs_7d}
          vs_30d={trendQuery.data.vs_30d}
          buckets={trendQuery.data.buckets}
        />
      )}

      <div style={{ display: 'flex', gap: 'var(--pad-2)', padding: 'var(--pad-3) var(--pad-4)', borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
        <select
          className="btn"
          value={filterProject}
          onChange={e => setFilterProject(e.target.value)}
          style={{ cursor: 'pointer' }}
        >
          <option value="">All projects</option>
          {projects.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <select
          className="btn"
          value={filterPriority}
          onChange={e => setFilterPriority(e.target.value)}
          style={{ cursor: 'pointer' }}
        >
          <option value="">All priorities</option>
          <option value="p0-critical">p0-critical</option>
          <option value="p1-high">p1-high</option>
          <option value="p2-medium">p2-medium</option>
          <option value="p3-low">p3-low</option>
        </select>
      </div>

      {query.isLoading && allRows.length === 0 ? (
        <div className="muted" style={{ padding: 'var(--pad-4)' }}>Loading…</div>
      ) : visible.length === 0 ? (
        <div className="muted" style={{ padding: 'var(--pad-4)' }}>No issues with recorded cost yet.</div>
      ) : (
        <table className="t">
          <thead>
            <tr>
              <th>Project</th>
              <th>Issue</th>
              <th>Priority</th>
              <th>State</th>
              <th>Rework factor</th>
              <th>Total points</th>
              <th>Stranded</th>
              <th>Last event</th>
            </tr>
          </thead>
          <tbody>
            {visible.map(row => (
              <tr key={`${row.project}-${row.issue_number}`}>
                <td className="mono" style={{ fontSize: 11 }}>{row.project}</td>
                <td>
                  {row.github_url ? (
                    <a
                      href={row.github_url}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: 'var(--fg-2)', textDecoration: 'none', fontFamily: 'var(--font-mono)', fontSize: 11 }}
                    >
                      #{row.issue_number}
                    </a>
                  ) : (
                    <span className="mono" style={{ color: 'var(--fg-3)', fontSize: 11 }}>#{row.issue_number}</span>
                  )}
                </td>
                <td className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>{row.priority}</td>
                <td className="mono" style={{ fontSize: 10, color: 'var(--fg-3)' }}>{row.state}</td>
                <td className="num" style={{ color: reworkColor(row.rework_factor), fontWeight: 500 }}>
                  {row.rework_factor.toFixed(2)}
                </td>
                <td className="num">{row.total_points}</td>
                <td className="num mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>{formatStranded(row.stranded_seconds)}</td>
                <td className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>{formatLastEvent(row.last_event_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {hasMore && (
        <div style={{ padding: 'var(--pad-4)', display: 'flex', justifyContent: 'center' }}>
          <button
            className="btn primary"
            onClick={() => setOffset(prev => prev + LIMIT)}
            disabled={query.isFetching}
          >
            {query.isFetching ? 'Loading…' : 'Load more'}
          </button>
        </div>
      )}
    </div>
  );
}
