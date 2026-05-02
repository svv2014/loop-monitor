/* global React, PipelineData, PMComponents, PMPanels */
const { useState, useMemo, useEffect } = React;
const { relTime, durationFmt, RoleTag, EventGlyph, useTick } = PMComponents;
const { NowStrip, Activity24h, ProjectCard, Leaderboard, ActivityFeed } = PMPanels;

// ====== OVERVIEW SCREEN ======
function OverviewScreen({ events, workers, setScreen, setSelectedProject, setSelectedWorker }) {
  const projects = useMemo(() => PipelineData.buildProjectStatus(events, workers), [events, workers]);
  const buckets  = useMemo(() => PipelineData.build24hBuckets(events), [events]);
  const completed = useMemo(() => events.filter(e => ['merge_done', 'judge_done', 'review_done', 'dev_done', 'po_done'].includes(e.event)).slice(0, 30), [events]);

  return (
    <>
      <NowStrip workers={workers} events={events}/>
      <div style={{ padding: 'var(--pad-4)', display: 'grid', gap: 'var(--pad-3)' }}>

        {/* Top row: 24h activity full width */}
        <Activity24h buckets={buckets}/>

        {/* Project status grid + leaderboard */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 'var(--pad-3)' }}>
          <div className="panel">
            <div className="panel-h">
              <span>Project status · {projects.length}</span>
              <span className="muted">{projects.filter(p => p.status === 'busy').length} busy</span>
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 1,
              background: 'var(--border)',
            }}>
              {projects.map(p => (
                <ProjectCard key={p.id} p={p} onClick={() => { setSelectedProject(p.id); setScreen('project'); }}/>
              ))}
            </div>
          </div>
          <Leaderboard events={events}/>
        </div>

        {/* Activity feed + completed jobs */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--pad-3)' }}>
          <ActivityFeed events={events}/>
          <div className="panel">
            <div className="panel-h"><span>Completed jobs · last 30</span></div>
            <div style={{ overflow: 'auto', maxHeight: 480 }}>
              {completed.map(e => (
                <div key={e.id} className="feed-row">
                  <EventGlyph event={e.event}/>
                  <div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span className="mono" style={{ color: `var(--role-${e.role})`, fontWeight: 500 }}>
                        {e.project}
                      </span>
                      <RoleTag role={e.role}/>
                      <span className="muted mono" style={{ fontSize: 11 }}>{e.model}</span>
                    </div>
                    <div className="muted mono" style={{ fontSize: 11, marginTop: 2 }}>
                      {e.event} · #{e.issue_num} · {durationFmt(e.duration_ms)}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    {e.points > 0 && <div className="mono" style={{ color: 'var(--accent)', fontSize: 12 }}>+{e.points}</div>}
                    <div className="muted mono" style={{ fontSize: 10 }}>{relTime(e.ts)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>
    </>
  );
}

// ====== ACTION QUEUE SCREEN ======
function QueueScreen({ events }) {
  useTick(1000);
  const [items] = useState(() => PipelineData.QUEUE);
  const [filter, setFilter] = useState('all');
  const filtered = filter === 'all' ? items : items.filter(i => i.priority === filter);
  const counts = items.reduce((acc, i) => { acc[i.priority] = (acc[i.priority] || 0) + 1; return acc; }, {});

  const PRI_COLOR = {
    critical: 'var(--fail)',
    high:     'var(--warn)',
    normal:   'var(--fg-2)',
    low:      'var(--fg-4)',
  };

  return (
    <>
      <div className="screen-h">
        <h1>Action Queue</h1>
        <span className="meta">{items.length} pending · longest wait {durationFmt(Math.max(...items.map(i => i.waiting_ms)))}</span>
      </div>

      {/* KPI strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', borderBottom: '1px solid var(--border)' }}>
        {['critical', 'high', 'normal', 'low'].map((p) => (
          <div key={p} style={{
            padding: 'var(--pad-3) var(--pad-4)',
            borderRight: '1px solid var(--border)',
          }}>
            <div className="mono" style={{
              fontSize: 10, textTransform: 'uppercase', letterSpacing: '.12em',
              color: PRI_COLOR[p], marginBottom: 4,
            }}>{p}</div>
            <div className="num" style={{ fontSize: 28, color: 'var(--fg)' }}>{counts[p] || 0}</div>
          </div>
        ))}
      </div>

      <div style={{ padding: 'var(--pad-4)' }}>
        <div className="panel">
          <div className="panel-h">
            <span>Pending tasks</span>
            <span className="actions">
              {['all', 'critical', 'high', 'normal', 'low'].map(p => (
                <button key={p}
                  className={`btn ${filter === p ? 'primary' : ''}`}
                  onClick={() => setFilter(p)}>{p}</button>
              ))}
            </span>
          </div>
          <table className="t">
            <thead>
              <tr>
                <th style={{ width: 90 }}>Priority</th>
                <th style={{ width: 80 }}>Role</th>
                <th>Project / Issue</th>
                <th>Title</th>
                <th style={{ width: 70 }}>Attempts</th>
                <th style={{ width: 100, textAlign: 'right' }}>Waiting</th>
                <th style={{ width: 100, textAlign: 'right' }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(it => (
                <tr key={it.id}>
                  <td>
                    <span className="tag" style={{
                      color: PRI_COLOR[it.priority],
                      borderColor: PRI_COLOR[it.priority],
                    }}>{it.priority}</span>
                  </td>
                  <td><RoleTag role={it.role}/></td>
                  <td className="mono" style={{ fontSize: 12 }}>
                    <span style={{ color: 'var(--fg)' }}>{it.project}</span>
                    <span className="muted"> #{it.issue_num}</span>
                  </td>
                  <td style={{ color: 'var(--fg-2)' }}>{it.title}</td>
                  <td className="num muted">{it.attempts}/3</td>
                  <td className="num muted" style={{ textAlign: 'right' }}>{durationFmt(it.waiting_ms)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn primary">dispatch</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// ====== PROJECT DETAIL ======
function ProjectDetail({ projectId, events, workers, setScreen, setSelectedProject }) {
  const projEvents = useMemo(() => events.filter(e => e.project === projectId), [events, projectId]);
  const buckets = useMemo(() => PipelineData.build24hBuckets(projEvents), [projEvents]);
  const board = useMemo(() => PipelineData.buildLeaderboard(projEvents, 'role'), [projEvents]);
  const totalPts = projEvents.reduce((a, e) => a + e.points, 0);
  const busyHere = workers.filter(w => w.project === projectId);
  const allProjects = PipelineData.PROJECTS;

  // Issue-level rollup
  const issues = useMemo(() => {
    const m = new Map();
    for (const e of projEvents) {
      if (!m.has(e.issue_num)) m.set(e.issue_num, { num: e.issue_num, events: [], lastTs: 0, status: 'open', pts: 0 });
      const row = m.get(e.issue_num);
      row.events.push(e);
      row.pts += e.points;
      if (e.ts > row.lastTs) row.lastTs = e.ts;
      if (e.event === 'merge_done') row.status = 'merged';
      else if (e.event === 'qa_fail' && row.status !== 'merged') row.status = 'failing';
    }
    return Array.from(m.values()).sort((a, b) => b.lastTs - a.lastTs).slice(0, 12);
  }, [projEvents]);

  return (
    <>
      <div className="screen-h" style={{ alignItems: 'center', display: 'flex', gap: 'var(--pad-3)' }}>
        <button className="btn" onClick={() => setScreen('overview')}>← Overview</button>
        <h1 style={{ flex: 1 }}>
          <span className="muted">project /</span> {projectId}
        </h1>
        <select
          className="mono"
          value={projectId}
          onChange={e => setSelectedProject(e.target.value)}
          style={{
            background: 'var(--bg-1)',
            color: 'var(--fg)',
            border: '1px solid var(--border)',
            padding: '4px 8px',
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
          }}>
          {allProjects.map(p => <option key={p.id}>{p.id}</option>)}
        </select>
        <span className="meta">{projEvents.length} events · {totalPts} pts</span>
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', borderBottom: '1px solid var(--border)' }}>
        {[
          ['Status', busyHere.length ? 'BUSY' : 'IDLE', busyHere.length ? 'var(--accent)' : 'var(--fg-3)'],
          ['Total points', totalPts, 'var(--fg)'],
          ['Active workers', busyHere.length, 'var(--fg)'],
          ['Events 24h', projEvents.filter(e => Date.now() - e.ts < 86400000).length, 'var(--fg)'],
          ['Open issues', issues.filter(i => i.status === 'open').length, 'var(--fg)'],
        ].map(([k, v, c]) => (
          <div key={k} style={{
            padding: 'var(--pad-3) var(--pad-4)',
            borderRight: '1px solid var(--border)',
          }}>
            <div className="mono" style={{
              fontSize: 10, textTransform: 'uppercase', letterSpacing: '.12em',
              color: 'var(--fg-3)', marginBottom: 4,
            }}>{k}</div>
            <div className="num" style={{ fontSize: 22, color: c }}>{v}</div>
          </div>
        ))}
      </div>

      <div style={{ padding: 'var(--pad-4)', display: 'grid', gap: 'var(--pad-3)' }}>
        <Activity24h buckets={buckets}/>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--pad-3)' }}>
          {/* Issues */}
          <div className="panel">
            <div className="panel-h"><span>Recent issues</span></div>
            <table className="t">
              <thead>
                <tr><th>#</th><th>Status</th><th>Events</th><th>Last</th><th style={{ textAlign: 'right' }}>Pts</th></tr>
              </thead>
              <tbody>
                {issues.map(i => (
                  <tr key={i.num}>
                    <td className="mono" style={{ color: 'var(--fg)' }}>#{i.num}</td>
                    <td>
                      <span className="tag" style={{
                        color: i.status === 'merged' ? 'var(--role-merge)'
                          : i.status === 'failing' ? 'var(--fail)' : 'var(--fg-3)',
                        borderColor: 'currentColor',
                      }}>{i.status}</span>
                    </td>
                    <td className="num muted">{i.events.length}</td>
                    <td className="muted mono" style={{ fontSize: 11 }}>{relTime(i.lastTs)} ago</td>
                    <td className="num" style={{ textAlign: 'right' }}>{i.pts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Per-role breakdown */}
          <div className="panel">
            <div className="panel-h"><span>Points by role</span></div>
            <div style={{ padding: 'var(--pad-3) var(--pad-4)', display: 'grid', gap: 10 }}>
              {board.map(r => {
                const max = Math.max(1, ...board.map(x => x.points));
                const pct = (r.points / max) * 100;
                return (
                  <div key={r.key} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 50px', alignItems: 'center', gap: 10 }}>
                    <RoleTag role={r.key}/>
                    <div style={{
                      height: 12,
                      background: 'var(--bg-2)',
                      position: 'relative',
                      overflow: 'hidden',
                    }}>
                      <div style={{
                        position: 'absolute', left: 0, top: 0, bottom: 0,
                        width: `${pct}%`,
                        background: `var(--role-${r.key})`,
                        opacity: 0.55,
                      }}/>
                    </div>
                    <span className="num" style={{ textAlign: 'right' }}>{r.points}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Event timeline */}
        <div className="panel">
          <div className="panel-h"><span>Event stream</span><span className="muted mono">{projEvents.length} total</span></div>
          <div style={{ overflow: 'auto', maxHeight: 360 }}>
            {projEvents.slice(0, 80).map(e => (
              <div key={e.id} className="feed-row">
                <EventGlyph event={e.event}/>
                <div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <RoleTag role={e.role}/>
                    <span className="mono">{e.event}</span>
                    <span className="muted mono" style={{ fontSize: 11 }}>· #{e.issue_num} · {e.agent}/{e.model}</span>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  {e.points > 0 && <div className="mono" style={{ color: 'var(--accent)' }}>+{e.points}</div>}
                  <div className="muted mono" style={{ fontSize: 10 }}>{relTime(e.ts)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ====== WORKER DETAIL ======
function WorkerDetail({ workerId, events, workers, setScreen }) {
  const [filter, setFilter] = useState(workerId || 'all-agents');

  // Roll up events by agent/model
  const byAgent = useMemo(() => {
    const m = new Map();
    for (const e of events) {
      const k = `${e.agent}/${e.model}`;
      if (!m.has(k)) m.set(k, {
        key: k, agent: e.agent, model: e.model,
        events: 0, points: 0, fails: 0, lastTs: 0,
        roles: new Set(),
      });
      const row = m.get(k);
      row.events += 1;
      row.points += e.points;
      if (e.event === 'qa_fail') row.fails += 1;
      if (e.ts > row.lastTs) row.lastTs = e.ts;
      row.roles.add(e.role);
    }
    return Array.from(m.values()).sort((a, b) => b.points - a.points);
  }, [events]);

  const selected = byAgent.find(a => a.key === filter) || byAgent[0];
  const selectedEvents = useMemo(
    () => events.filter(e => `${e.agent}/${e.model}` === selected?.key).slice(0, 60),
    [events, selected]
  );

  return (
    <>
      <div className="screen-h" style={{ alignItems: 'center', display: 'flex', gap: 'var(--pad-3)' }}>
        <button className="btn" onClick={() => setScreen('overview')}>← Overview</button>
        <h1 style={{ flex: 1 }}>
          <span className="muted">worker /</span> {selected?.key || '—'}
        </h1>
        <span className="meta">{byAgent.length} unique agents</span>
      </div>

      <div className="detail-grid" style={{ alignItems: 'stretch', minHeight: 'calc(100vh - 140px)' }}>
        {/* Left: list of agents */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="panel" style={{ border: 'none', borderBottom: '1px solid var(--border)' }}>
            <div className="panel-h"><span>All agents</span></div>
            <div style={{ overflow: 'auto', maxHeight: '70vh' }}>
              {byAgent.map(a => (
                <div key={a.key}
                  onClick={() => setFilter(a.key)}
                  style={{
                    padding: 'var(--pad-3) var(--pad-4)',
                    borderBottom: '1px solid var(--border)',
                    cursor: 'pointer',
                    background: filter === a.key ? 'var(--bg-2)' : 'transparent',
                    borderLeft: filter === a.key ? '2px solid var(--accent)' : '2px solid transparent',
                    display: 'grid',
                    gridTemplateColumns: '1fr auto',
                    gap: 'var(--pad-2)',
                    alignItems: 'center',
                  }}>
                  <div>
                    <div className="mono" style={{ fontSize: 13, color: 'var(--fg)' }}>{a.model}</div>
                    <div className="muted mono" style={{ fontSize: 10 }}>
                      {a.agent} · {Array.from(a.roles).join(', ')}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div className="num" style={{ color: 'var(--accent)' }}>{a.points}</div>
                    <div className="muted mono" style={{ fontSize: 10 }}>{a.events} ev</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: detail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--pad-3)', padding: 'var(--pad-4)' }}>
          {selected && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1, background: 'var(--border)' }}>
                {[
                  ['Total events', selected.events],
                  ['Points', selected.points],
                  ['QA fails', selected.fails],
                  ['Last seen', relTime(selected.lastTs) + ' ago'],
                ].map(([k, v]) => (
                  <div key={k} style={{ background: 'var(--bg-1)', padding: 'var(--pad-3)' }}>
                    <div className="mono" style={{
                      fontSize: 10, textTransform: 'uppercase', letterSpacing: '.12em',
                      color: 'var(--fg-3)', marginBottom: 4,
                    }}>{k}</div>
                    <div className="num" style={{ fontSize: 20, color: 'var(--fg)' }}>{v}</div>
                  </div>
                ))}
              </div>

              <div className="panel">
                <div className="panel-h"><span>Recent events for {selected.key}</span></div>
                <div style={{ overflow: 'auto', maxHeight: 480 }}>
                  {selectedEvents.map(e => (
                    <div key={e.id} className="feed-row">
                      <EventGlyph event={e.event}/>
                      <div>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          <RoleTag role={e.role}/>
                          <span className="mono">{e.event}</span>
                          <span className="muted mono" style={{ fontSize: 11 }}>· {e.project}#{e.issue_num}</span>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        {e.points > 0 && <div className="mono" style={{ color: 'var(--accent)' }}>+{e.points}</div>}
                        <div className="muted mono" style={{ fontSize: 10 }}>{relTime(e.ts)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

window.PMScreens = { OverviewScreen, QueueScreen, ProjectDetail, WorkerDetail };
