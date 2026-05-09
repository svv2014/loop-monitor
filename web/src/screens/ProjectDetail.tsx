import { useEffect, useMemo, useState } from 'react';
import PrMonitorTable from '../components/PrMonitorTable';
import type { Worker, FeedItem, PipelineRun, PRMonitorEntry } from '../lib/types';

interface IssueRollup {
  num: number;
  runCount: number;
  pts: number;
  lastAt: string | null;
  status: 'merged' | 'failing' | 'open';
}

interface ProjectDetailProps {
  projectId: string;
  allProjectIds: string[];
  onBack: () => void;
  onProjectChange: (id: string) => void;
}

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

export default function ProjectDetail({ projectId, allProjectIds, onBack, onProjectChange }: ProjectDetailProps) {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [prs, setPrs] = useState<PRMonitorEntry[]>([]);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [active, setActive] = useState<Worker[]>([]);
  const [prsLoading, setPrsLoading] = useState(true);
  const [prsError, setPrsError] = useState(false);
  const [includeFinishedPrs, setIncludeFinishedPrs] = useState(false);

  // Fetch runs
  useEffect(() => {
    setRuns([]);
    fetch(`/api/runs/${encodeURIComponent(projectId)}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: PipelineRun[]) => setRuns(data))
      .catch(() => setRuns([]));
  }, [projectId]);

  // Fetch PRs (re-fetch on includeFinished toggle)
  useEffect(() => {
    setPrsLoading(true);
    setPrsError(false);
    fetch(`/api/projects/${encodeURIComponent(projectId)}/prs?include_finished=${includeFinishedPrs}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: PRMonitorEntry[]) => { setPrs(data); setPrsLoading(false); })
      .catch(() => { setPrsError(true); setPrsLoading(false); });
  }, [projectId, includeFinishedPrs]);

  // Fetch feed (all; filter client-side by project)
  useEffect(() => {
    setFeed([]);
    fetch('/api/feed')
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: FeedItem[]) => setFeed(data.filter(e => e.project === projectId)))
      .catch(() => setFeed([]));
  }, [projectId]);

  // Fetch active workers
  useEffect(() => {
    fetch('/api/active')
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: Worker[]) => setActive(data))
      .catch(() => setActive([]));
    const id = setInterval(() => {
      fetch('/api/active')
        .then(r => r.ok ? r.json() : Promise.reject(r.status))
        .then((data: Worker[]) => setActive(data))
        .catch(() => undefined);
    }, 10_000);
    return () => clearInterval(id);
  }, []);

  const busyWorkers = active.filter(w => w.project === projectId);
  const isBusy = busyWorkers.length > 0;

  // Issue-level rollup from runs
  const issues = useMemo((): IssueRollup[] => {
    const m = new Map<number, IssueRollup>();
    for (const r of runs) {
      if (r.issue_number == null) continue;
      const existing = m.get(r.issue_number);
      let status: IssueRollup['status'] = 'open';
      if (r.outcome === 'merged' || r.outcome === 'clean') status = 'merged';
      else if (r.outcome != null) status = 'failing';
      if (!existing) {
        m.set(r.issue_number, {
          num: r.issue_number,
          runCount: 1,
          pts: r.total_bounty ?? 0,
          lastAt: r.completed_at ?? r.started_at,
          status,
        });
      } else {
        existing.runCount += 1;
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
  const roleBoard = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of feed) {
      if (e.role) m.set(e.role, (m.get(e.role) ?? 0) + 1);
    }
    return Array.from(m.entries())
      .map(([role, pts]) => ({ role, pts }))
      .sort((a, b) => b.pts - a.pts);
  }, [feed]);

  const maxRolePts = Math.max(1, ...roleBoard.map(r => r.pts));
  const totalPts = runs.reduce((a, r) => a + (r.total_bounty ?? 0), 0);
  const events24h = feed.filter(e => (e.age_seconds ?? Infinity) < 86400).length;
  const openIssues = issues.filter(i => i.status === 'open').length;

  const kpiCells: [string, string | number, string][] = [
    ['Status',         isBusy ? 'BUSY' : 'IDLE',    isBusy ? 'var(--accent)' : 'var(--fg-3)'],
    ['Total points',   totalPts,                     'var(--fg)'],
    ['Active workers', busyWorkers.length,           'var(--fg)'],
    ['Events 24h',     events24h,                    'var(--fg)'],
    ['Open issues',    openIssues,                   'var(--fg)'],
  ];

  return (
    <div data-testid="project-detail">
      {/* Screen header */}
      <div className="screen-h" style={{ display: 'flex', alignItems: 'center', gap: 'var(--pad-3)', padding: 'var(--pad-2) var(--pad-4)' }}>
        <button className="btn" onClick={onBack}>← Overview</button>
        <h1 style={{ flex: 1, margin: 0, fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500, letterSpacing: '0.04em' }}>
          <span className="muted">project /</span> {projectId}
        </h1>
        <select
          className="btn"
          value={projectId}
          onChange={e => onProjectChange(e.target.value)}
          aria-label="Switch project"
          style={{ cursor: 'pointer' }}
        >
          {allProjectIds.map(id => <option key={id} value={id}>{id}</option>)}
        </select>
        <span className="meta">{feed.length} events · {totalPts} pts</span>
      </div>

      {/* KPI strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', borderBottom: '1px solid var(--border)' }}>
        {kpiCells.map(([k, v, c]) => (
          <div key={k} style={{ padding: 'var(--pad-3) var(--pad-4)', borderRight: '1px solid var(--border)' }}>
            <div className="mono" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--fg-3)', marginBottom: 4 }}>{k}</div>
            <div className="num" style={{ fontSize: 22, color: c }}>{v}</div>
          </div>
        ))}
      </div>

      {/* Body */}
      <div style={{ padding: 'var(--pad-4)', display: 'grid', gap: 'var(--pad-3)' }}>

        {/* Two-column: issues + role chart */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--pad-3)' }}>

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
                  <tr><td colSpan={5} className="muted" style={{ textAlign: 'center', padding: 'var(--pad-3)' }}>No runs yet</td></tr>
                )}
                {issues.map(i => (
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
                    <td className="num muted" style={{ textAlign: 'right' }}>{i.runCount}</td>
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
            <div style={{ padding: 'var(--pad-3) var(--pad-4)', display: 'grid', gap: 10 }}>
              {roleBoard.length === 0 && (
                <div className="muted" style={{ fontSize: 12, textAlign: 'center' }}>No events yet</div>
              )}
              {roleBoard.map(r => {
                const pct = (r.pts / maxRolePts) * 100;
                const color = ROLE_COLORS[r.role] ?? 'var(--fg-3)';
                return (
                  <div key={r.role} style={{ display: 'grid', gridTemplateColumns: '90px 1fr 50px', alignItems: 'center', gap: 10 }}>
                    <span className="tag" style={{ color, borderColor: 'currentColor', textAlign: 'center' }}>
                      {r.role}
                    </span>
                    <div style={{ height: 12, background: 'var(--bg-2)', position: 'relative', overflow: 'hidden' }}>
                      <div style={{
                        position: 'absolute', left: 0, top: 0, bottom: 0,
                        width: `${pct}%`,
                        background: color,
                        opacity: 0.55,
                        transition: 'width 300ms ease',
                      }} />
                    </div>
                    <span className="num" style={{ textAlign: 'right', color: 'var(--fg-2)' }}>{r.pts}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* PR Monitor */}
        <PrMonitorTable
          rows={prs}
          loading={prsLoading}
          error={prsError}
          includeFinished={includeFinishedPrs}
          onIncludeFinishedChange={setIncludeFinishedPrs}
        />

        {/* Event stream */}
        <div className="panel">
          <div className="panel-h">
            <span>Event stream</span>
            <span className="muted mono">{feed.length} total</span>
          </div>
          <div style={{ overflow: 'auto', maxHeight: 360 }}>
            {feed.length === 0 && (
              <div className="muted" style={{ padding: 'var(--pad-3)', fontSize: 12, textAlign: 'center' }}>No events for this project</div>
            )}
            {feed.slice(0, 80).map(e => (
              <div key={e.id} className="feed-row">
                <span className="mono" style={{ color: ROLE_COLORS[e.role] ?? 'var(--fg-3)', fontSize: 13 }}>
                  {EVENT_GLYPHS[e.event_type] ?? '·'}
                </span>
                <div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className="tag" style={{ color: ROLE_COLORS[e.role] ?? 'var(--fg-3)', borderColor: 'currentColor' }}>
                      {e.role}
                    </span>
                    <span className="mono">{e.event_type}</span>
                    {e.issue_number != null && (
                      <span className="muted mono" style={{ fontSize: 11 }}>· #{e.issue_number}</span>
                    )}
                    {e.model && (
                      <span className="muted mono" style={{ fontSize: 11 }}>· {e.model}</span>
                    )}
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
