import { useMemo, useState } from 'react';
import type { PrMonitorRow } from '../api/client';
import styles from './PrMonitorTable.module.css';

interface Props {
  rows: PrMonitorRow[];
  isLoading?: boolean;
  isError?: boolean;
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

function timeClass(secs: number | null): string {
  if (secs == null) return '';
  if (secs > 86400) return styles.timeDanger;
  if (secs > 21600) return styles.timeWarn;
  return styles.timeFresh;
}

function stageClass(stage: string | null): string {
  if (!stage) return '';
  const s = stage.toLowerCase();
  if (s.includes('fail') || s.includes('rework')) return styles.stageFail;
  if (s.includes('merge')) return styles.stageMerge;
  if (s.includes('qa')) return styles.stageQa;
  if (s.includes('review')) return styles.stageReview;
  if (s.includes('dev')) return styles.stageDev;
  if (s.includes('po')) return styles.stagePo;
  return '';
}

export function PrMonitorTable({ rows, isLoading, isError }: Props) {
  const [stageFilter, setStageFilter] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('age');
  const [includeFinished, setIncludeFinished] = useState(false);

  const stages = useMemo(
    () => Array.from(new Set(rows.map((r) => r.stage).filter(Boolean))).sort() as string[],
    [rows],
  );

  const visible = useMemo(() => {
    let r = rows.slice();
    if (!includeFinished) r = r.filter((row) => !row.is_finished);
    if (stageFilter) r = r.filter((row) => row.stage === stageFilter);
    r.sort((a, b) => {
      if (sortMode === 'stage') return (a.stage ?? '').localeCompare(b.stage ?? '');
      const av = a.time_in_stage_seconds ?? -1;
      const bv = b.time_in_stage_seconds ?? -1;
      return sortMode === 'age-desc' ? av - bv : bv - av;
    });
    return r;
  }, [rows, stageFilter, sortMode, includeFinished]);

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <span>PR Monitor</span>
        <span className={styles.controls}>
          <select
            className={styles.select}
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
            aria-label="Filter by stage"
          >
            <option value="">All stages</option>
            {stages.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select
            className={styles.select}
            value={sortMode}
            onChange={(e) => setSortMode(e.target.value as SortMode)}
            aria-label="Sort order"
          >
            <option value="age">Oldest first</option>
            <option value="age-desc">Newest first</option>
            <option value="stage">By stage</option>
          </select>
          <label className={styles.checkLabel}>
            <input
              type="checkbox"
              checked={includeFinished}
              onChange={(e) => setIncludeFinished(e.target.checked)}
            />
            {' '}finished
          </label>
        </span>
      </div>

      <table className="t">
        <thead>
          <tr>
            <th style={{ width: 70 }}>PR</th>
            <th>Title / Branch</th>
            <th style={{ width: 130 }}>Stage</th>
            <th style={{ width: 90, textAlign: 'right' }}>In stage</th>
            <th style={{ width: 60, textAlign: 'right' }}>Retries</th>
            <th style={{ width: 120 }}>Last event</th>
            <th style={{ width: 28 }}></th>
          </tr>
        </thead>
        <tbody>
          {isLoading && (
            <tr>
              <td colSpan={7} className={styles.empty}>Loading…</td>
            </tr>
          )}
          {isError && (
            <tr>
              <td colSpan={7} className={styles.errorState}>Failed to load PRs</td>
            </tr>
          )}
          {!isLoading && !isError && visible.length === 0 && (
            <tr>
              <td colSpan={7} className={styles.empty}>No PRs tracked yet</td>
            </tr>
          )}
          {visible.map((r) => (
            <tr key={r.pr_number} className={r.is_finished ? styles.rowFinished : undefined}>
              <td className={styles.prNum}>
                <span className="mono">#{r.pr_number}</span>
                {r.is_draft && <span className={styles.badgeDraft}>draft</span>}
                {r.is_finished && <span className={styles.badgeDone}>done</span>}
              </td>
              <td>
                <div className={styles.titleCell}>{r.title ?? '—'}</div>
                {r.branch && (
                  <div className={styles.branch}>{r.branch}</div>
                )}
              </td>
              <td>
                <span className={`${styles.stageBadge} ${stageClass(r.stage)}`}>
                  {r.stage ?? '—'}
                </span>
              </td>
              <td className={`num ${timeClass(r.time_in_stage_seconds)}`} style={{ textAlign: 'right' }}>
                {fmtDuration(r.time_in_stage_seconds)}
              </td>
              <td className="num muted" style={{ textAlign: 'right' }}>{r.retry_count}</td>
              <td className={styles.lastEvent}>
                <span className="mono">{r.last_event ?? '—'}</span>
              </td>
              <td>
                {r.github_url && (
                  <a
                    href={r.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.ghLink}
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
