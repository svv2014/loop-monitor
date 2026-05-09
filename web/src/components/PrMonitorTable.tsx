import { useMemo, useState } from 'react';
import type { PRMonitorEntry } from '../lib/types';

interface PrMonitorTableProps {
  rows: PRMonitorEntry[];
  loading: boolean;
  error: boolean;
  includeFinished: boolean;
  onIncludeFinishedChange: (v: boolean) => void;
}

type SortMode = 'age' | 'age-desc' | 'stage';

function fmtDuration(secs: number | null): string {
  if (secs == null) return '—';
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return s ? `${m}m ${s}s` : `${m}m`;
  }
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}

function timeColor(secs: number | null): string {
  if (secs == null) return 'var(--fg-3)';
  if (secs > 86400) return 'var(--fail)';
  if (secs > 21600) return 'var(--warn)';
  return 'var(--pass)';
}

const STAGE_ROLE: Record<string, string> = {
  'in-development': 'dev', 'dev-complete': 'dev', 'dev-failed': 'dev',
  'in-review': 'reviewer', 'review-complete': 'reviewer', 'review-failed': 'reviewer',
  'needs-rework': 'qa', 'rework-complete': 'qa', 'rework-failed': 'qa',
  'in-qa': 'qa', 'qa-passed': 'qa', 'qa-complete': 'qa',
  'merging': 'merge', 'merged': 'merge',
  'in-po': 'po', 'po-approved': 'po', 'po-failed': 'po',
};

function StageBadge({ stage }: { stage: string | null }) {
  if (!stage) return <span className="tag dim">—</span>;
  const role = STAGE_ROLE[stage];
  const color = role ? `var(--role-${role})` : 'var(--fg-3)';
  return <span className="tag" style={{ color, borderColor: 'currentColor' }}>{stage}</span>;
}

export default function PrMonitorTable({ rows, loading, error, includeFinished, onIncludeFinishedChange }: PrMonitorTableProps) {
  const [stageFilter, setStageFilter] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('age');

  const stages = useMemo(
    () => Array.from(new Set(rows.map(r => r.stage).filter((s): s is string => s != null))).sort(),
    [rows],
  );

  const visible = useMemo(() => {
    let r = rows.slice();
    if (stageFilter) r = r.filter(row => row.stage === stageFilter);
    r.sort((a, b) => {
      if (sortMode === 'stage') return (a.stage ?? '').localeCompare(b.stage ?? '');
      const av = a.time_in_stage_seconds ?? -1;
      const bv = b.time_in_stage_seconds ?? -1;
      return sortMode === 'age-desc' ? av - bv : bv - av;
    });
    return r;
  }, [rows, stageFilter, sortMode]);

  return (
    <div className="panel">
      <div className="panel-h">
        <span>PR Monitor</span>
        <span className="actions">
          <select
            className="btn"
            style={{ cursor: 'pointer' }}
            value={stageFilter}
            onChange={e => setStageFilter(e.target.value)}
            aria-label="Filter by stage"
          >
            <option value="">All stages</option>
            {stages.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select
            className="btn"
            style={{ cursor: 'pointer' }}
            value={sortMode}
            onChange={e => setSortMode(e.target.value as SortMode)}
            aria-label="Sort order"
          >
            <option value="age">Oldest first</option>
            <option value="age-desc">Newest first</option>
            <option value="stage">By stage</option>
          </select>
          <label style={{
            display: 'flex', alignItems: 'center', gap: 4,
            fontFamily: 'var(--font-mono)', fontSize: 10,
            textTransform: 'uppercase', letterSpacing: '0.08em',
            color: 'var(--fg-3)', cursor: 'pointer',
          }}>
            <input
              type="checkbox"
              checked={includeFinished}
              onChange={e => onIncludeFinishedChange(e.target.checked)}
            />
            finished
          </label>
        </span>
      </div>

      <table className="t">
        <thead>
          <tr>
            <th style={{ width: 70 }}>PR</th>
            <th>Title / Branch</th>
            <th style={{ width: 140 }}>Stage</th>
            <th style={{ width: 90, textAlign: 'right' }}>In stage</th>
            <th style={{ width: 60, textAlign: 'right' }}>Retries</th>
            <th style={{ width: 120 }}>Last event</th>
            <th style={{ width: 28 }}></th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr><td colSpan={7} className="muted" style={{ textAlign: 'center', padding: 'var(--pad-3)' }}>Loading…</td></tr>
          )}
          {error && (
            <tr><td colSpan={7} style={{ color: 'var(--fail)', textAlign: 'center', padding: 'var(--pad-3)' }}>Failed to load PRs</td></tr>
          )}
          {!loading && !error && visible.length === 0 && (
            <tr><td colSpan={7} className="muted" style={{ textAlign: 'center', padding: 'var(--pad-3)' }}>No PRs tracked yet</td></tr>
          )}
          {visible.map(r => (
            <tr key={r.pr_number} style={{ opacity: r.is_finished ? 0.5 : 1 }}>
              <td>
                <span className="mono" style={{ color: 'var(--fg)' }}>#{r.pr_number}</span>
                {r.is_draft && <span className="tag dim" style={{ marginLeft: 4 }}>draft</span>}
                {r.is_finished && <span className="tag" style={{ marginLeft: 4, color: 'var(--pass)', borderColor: 'var(--pass)' }}>done</span>}
              </td>
              <td>
                <div style={{ color: 'var(--fg-2)', fontSize: 12 }}>{r.title ?? '—'}</div>
                {r.branch && <div className="mono dim" style={{ fontSize: 10, marginTop: 2 }}>{r.branch}</div>}
              </td>
              <td><StageBadge stage={r.stage} /></td>
              <td className="num" style={{ textAlign: 'right', color: timeColor(r.time_in_stage_seconds) }}>
                {fmtDuration(r.time_in_stage_seconds)}
              </td>
              <td className="num muted" style={{ textAlign: 'right' }}>{r.retry_count}</td>
              <td className="mono muted" style={{ fontSize: 11 }}>{r.last_event ?? '—'}</td>
              <td>
                {r.github_url && (
                  <a
                    href={r.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="muted"
                    style={{ fontSize: 11, textDecoration: 'none', transition: 'color 150ms' }}
                    aria-label={`Open PR #${r.pr_number} on GitHub`}
                  >↗</a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
