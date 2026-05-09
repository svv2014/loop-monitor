import { useMemo, useState } from 'react';
import { PrMonitorTable } from '../components/PrMonitorTable';
import { useActiveWorkers, useProjectFeed, useProjectPrs, useProjectRuns } from '../hooks/useProjectDetail';
import type { Screen } from '../router';
import styles from './ProjectDetail.module.css';

interface Props {
  projectId: string;
  setScreen: (screen: Screen) => void;
  setProjectId: (id: string) => void;
  allProjectIds: string[];
}

function relTime(isoStr: string | null): string {
  if (!isoStr) return '—';
  const d = new Date(isoStr.includes('T') ? isoStr : isoStr + 'Z');
  const secs = Math.floor((Date.now() - d.getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h`;
  return `${Math.floor(secs / 86400)}d`;
}

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

interface IssueRollup {
  num: number;
  eventCount: number;
  pts: number;
  lastAt: string | null;
  status: 'merged' | 'failing' | 'open';
}

interface RoleBarRow {
  role: string;
  points: number;
}

export function ProjectDetail({ projectId, setScreen, setProjectId, allProjectIds }: Props) {
  const [prIncludeFinished, setPrIncludeFinished] = useState(false);

  const runsQuery = useProjectRuns(projectId);
  const prsQuery = useProjectPrs(projectId, prIncludeFinished);
  const feedQuery = useProjectFeed(projectId);
  const activeQuery = useActiveWorkers();

  const runs = runsQuery.data ?? [];
  const feed = feedQuery.data ?? [];
  const active = activeQuery.data ?? [];

  const busyWorkers = active.filter((w) => w.project === projectId);
  const isBusy = busyWorkers.length > 0;

  // Issue-level rollup from runs
  const issues = useMemo((): IssueRollup[] => {
    const m = new Map<number, IssueRollup>();
    for (const r of runs) {
      if (r.issue_number == null) continue;
      const existing = m.get(r.issue_number);
      let status: IssueRollup['status'] = 'open';
      if (r.outcome === 'merged' || r.outcome === 'clean') status = 'merged';
      else if (r.outcome != null && r.outcome !== 'clean') status = 'failing';
      if (!existing) {
        m.set(r.issue_number, {
          num: r.issue_number,
          eventCount: 1,
          pts: r.total_bounty ?? 0,
          lastAt: r.completed_at ?? r.started_at,
          status,
        });
      } else {
        existing.eventCount += 1;
        existing.pts += r.total_bounty ?? 0;
        const ts = r.completed_at ?? r.started_at;
        if (ts && (!existing.lastAt || ts > existing.lastAt)) existing.lastAt = ts;
        if (status === 'merged') existing.status = 'merged';
        else if (status === 'failing' && existing.status !== 'merged') existing.status = 'failing';
      }
    }
    return Array.from(m.values())
      .sort((a, b) => (b.lastAt ?? '').localeCompare(a.lastAt ?? ''))
      .slice(0, 12);
  }, [runs]);

  // Points by role from feed events
  const roleBoard = useMemo((): RoleBarRow[] => {
    const m = new Map<string, number>();
    for (const e of feed) {
      if (!e.role) continue;
      m.set(e.role, (m.get(e.role) ?? 0) + 1);
    }
    return Array.from(m.entries())
      .map(([role, points]) => ({ role, points }))
      .sort((a, b) => b.points - a.points);
  }, [feed]);

  const maxRolePoints = Math.max(1, ...roleBoard.map((r) => r.points));

  const totalPts = runs.reduce((a, r) => a + (r.total_bounty ?? 0), 0);
  const events24h = feed.filter((e) => (e.age_seconds ?? Infinity) < 86400).length;
  const openIssues = issues.filter((i) => i.status === 'open').length;

  const ROLE_COLORS: Record<string, string> = {
    po: 'var(--role-po)',
    dev: 'var(--role-dev)',
    qa: 'var(--role-qa)',
    reviewer: 'var(--role-reviewer)',
    merge: 'var(--role-merge)',
    judge: 'var(--role-judge)',
  };

  const EVENT_GLYPHS: Record<string, string> = {
    dev_done: '✓', dev_failed: '✗', dev_start: '▸',
    review_done: '✓', review_failed: '✗', review_start: '▸',
    qa_pass: '✓', qa_fail: '✗', qa_start: '▸',
    merge_done: '◆', merge_start: '▸',
    po_done: '★', po_failed: '✗', po_start: '▸',
    rework_start: '↺', rework_done: '✓',
  };

  function eventGlyph(eventType: string): string {
    return EVENT_GLYPHS[eventType] ?? '·';
  }

  return (
    <div className={styles.root} data-testid="project-detail">
      {/* Screen header */}
      <div className={styles.screenHeader}>
        <button className="btn" onClick={() => setScreen('overview')}>← Overview</button>
        <h1 className={styles.title}>
          <span className="muted">project /</span> {projectId}
        </h1>
        <select
          className={`mono ${styles.projectSelect}`}
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          aria-label="Switch project"
        >
          {allProjectIds.map((id) => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
        <span className={styles.meta}>{feed.length} events · {totalPts} pts</span>
      </div>

      {/* KPI strip */}
      <div className={styles.kpiStrip}>
        {([
          ['Status',         isBusy ? 'BUSY' : 'IDLE',    isBusy ? 'var(--accent)' : 'var(--fg-3)'],
          ['Total points',   totalPts,                     'var(--fg)'],
          ['Active workers', busyWorkers.length,           'var(--fg)'],
          ['Events 24h',     events24h,                    'var(--fg)'],
          ['Open issues',    openIssues,                   'var(--fg)'],
        ] as [string, string | number, string][]).map(([k, v, c]) => (
          <div key={k} className={styles.kpiCell}>
            <div className={styles.kpiLabel}>{k}</div>
            <div className={`num ${styles.kpiValue}`} style={{ color: c }}>{v}</div>
          </div>
        ))}
      </div>

      {/* Main content */}
      <div className={styles.body}>

        {/* Row: issues + role breakdown */}
        <div className={styles.twoCol}>
          {/* Recent issues */}
          <div className="panel">
            <div className="panel-h">
              <span>Recent issues</span>
              <span className="muted">{issues.length} tracked</span>
            </div>
            <table className="t">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Runs</th>
                  <th>Last</th>
                  <th style={{ textAlign: 'right' }}>Pts</th>
                </tr>
              </thead>
              <tbody>
                {issues.length === 0 && (
                  <tr>
                    <td colSpan={5} className={styles.emptyCell}>No runs yet</td>
                  </tr>
                )}
                {issues.map((i) => (
                  <tr key={i.num}>
                    <td className="mono" style={{ color: 'var(--fg)' }}>#{i.num}</td>
                    <td>
                      <span className="tag" style={{
                        color: i.status === 'merged'  ? 'var(--role-merge)'
                             : i.status === 'failing' ? 'var(--fail)'
                             : 'var(--fg-3)',
                        borderColor: 'currentColor',
                      }}>{i.status}</span>
                    </td>
                    <td className="num muted" style={{ textAlign: 'right' }}>{i.eventCount}</td>
                    <td className="muted mono" style={{ fontSize: 11 }}>
                      {i.lastAt ? `${relTime(i.lastAt)} ago` : '—'}
                    </td>
                    <td className="num" style={{ textAlign: 'right' }}>{i.pts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Points by role */}
          <div className="panel">
            <div className="panel-h"><span>Points by role</span></div>
            <div className={styles.roleBarGrid}>
              {roleBoard.length === 0 && (
                <div className={styles.emptyCell}>No events yet</div>
              )}
              {roleBoard.map((r) => {
                const pct = (r.points / maxRolePoints) * 100;
                const color = ROLE_COLORS[r.role] ?? 'var(--fg-3)';
                return (
                  <div key={r.role} className={styles.roleBarRow}>
                    <span className="tag" style={{ color, borderColor: 'currentColor', width: 80, textAlign: 'center' }}>
                      {r.role}
                    </span>
                    <div className={styles.roleBarTrack}>
                      <div
                        className={styles.roleBarFill}
                        style={{ width: `${pct}%`, background: color, opacity: 0.55 }}
                      />
                    </div>
                    <span className="num" style={{ textAlign: 'right', minWidth: 40, color: 'var(--fg-2)' }}>
                      {r.points}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* PR Monitor */}
        <PrMonitorTable
          rows={prsQuery.data ?? []}
          isLoading={prsQuery.isLoading}
          isError={prsQuery.isError}
        />

        {/* Event stream */}
        <div className="panel">
          <div className="panel-h">
            <span>Event stream</span>
            <span className="muted mono">{feed.length} total</span>
          </div>
          <div className={styles.feedScroll}>
            {feed.length === 0 && (
              <div className={styles.emptyFeed}>No events for this project</div>
            )}
            {feed.slice(0, 80).map((e) => (
              <div key={e.id} className="feed-row">
                <span className="mono" style={{ color: ROLE_COLORS[e.role] ?? 'var(--fg-3)', width: 13 }}>
                  {eventGlyph(e.event_type)}
                </span>
                <div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className="tag" style={{
                      color: ROLE_COLORS[e.role] ?? 'var(--fg-3)',
                      borderColor: 'currentColor',
                    }}>{e.role}</span>
                    <span className="mono">{e.event_type}</span>
                    <span className="muted mono" style={{ fontSize: 11 }}>
                      {e.issue_number != null ? `· #${e.issue_number}` : ''}
                      {e.model ? ` · ${e.model}` : ''}
                    </span>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="muted mono" style={{ fontSize: 10 }}>
                    {e.age_seconds != null ? `${fmtDuration(e.age_seconds)} ago` : relTime(e.created_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
