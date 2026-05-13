// TODO(#113): capture reference screenshot once visual-diff harness lands
import { useState, useMemo, useEffect } from 'react';
import { fetchFeed } from '../lib/api';
import type { FeedItem } from '../lib/types';

function relTime(isoStr: string, ageSeconds: number | null): string {
  const secs = ageSeconds ?? Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h`;
  return `${Math.floor(secs / 86400)}d`;
}

const EVENT_GLYPHS: Record<string, string> = {
  po_start: '▸',    po_done: '✓',
  dev_start: '▸',   dev_done: '✓',
  qa_start: '▸',    qa_pass: '✓',  qa_fail: '✗',
  review_start: '▸', review_done: '✓',
  merge_start: '▸', merge_done: '◆',
  judge_start: '▸', judge_done: '★',
};

function glyphColor(eventType: string, role: string): string {
  return eventType.includes('_fail') || eventType.includes('_failed')
    ? 'var(--fail)'
    : `var(--role-${role})`;
}

interface AgentRow {
  key: string;
  role: string;
  model: string | null;
  events: number;
  fails: number;
  lastTs: number;
  lastIso: string;
  lastAge: number | null;
  roles: Set<string>;
}

export default function WorkerDetail() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    let cancelled = false;
    function load() {
      fetchFeed()
        .then(data => { if (!cancelled) { setItems(data); setLoading(false); } })
        .catch(() => { if (!cancelled) setLoading(false); });
    }
    load();
    const id = setInterval(load, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const byAgent = useMemo((): AgentRow[] => {
    const m = new Map<string, AgentRow>();
    for (const e of items) {
      const k = `${e.role}/${e.model ?? ''}`;
      if (!m.has(k)) {
        m.set(k, {
          key: k, role: e.role, model: e.model,
          events: 0, fails: 0, lastTs: 0,
          lastIso: e.created_at, lastAge: e.age_seconds,
          roles: new Set(),
        });
      }
      const row = m.get(k)!;
      row.events += 1;
      if (e.event_type.includes('_fail')) row.fails += 1;
      const ts = new Date(e.created_at).getTime();
      if (ts > row.lastTs) {
        row.lastTs = ts;
        row.lastIso = e.created_at;
        row.lastAge = e.age_seconds;
      }
      row.roles.add(e.role);
    }
    return Array.from(m.values()).sort((a, b) => b.events - a.events);
  }, [items]);

  const selectedKey = filter || byAgent[0]?.key;
  const selected = byAgent.find(a => a.key === selectedKey) ?? byAgent[0];
  const selectedItems = useMemo(
    () => items.filter(e => `${e.role}/${e.model ?? ''}` === selected?.key).slice(0, 60),
    [items, selected],
  );

  if (loading) {
    return (
      <div style={{ padding: 'var(--pad-4)', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
        Loading…
      </div>
    );
  }

  return (
    <>
      <div className="screen-h">
        <h1>
          <span style={{ color: 'var(--fg-3)' }}>worker /</span>{' '}
          {selected?.key ?? '—'}
        </h1>
        <span className="meta">{byAgent.length} unique agents</span>
      </div>

      <div
        className="detail-grid"
        style={{ alignItems: 'stretch', minHeight: 'calc(100vh - 140px)' }}
      >
        {/* Left: agent list */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="panel" style={{ border: 'none', borderBottom: '1px solid var(--border)', flex: 1 }}>
            <div className="panel-h"><span>All agents</span></div>
            <div style={{ overflow: 'auto', maxHeight: '70vh' }}>
              {byAgent.map(a => (
                <div
                  key={a.key}
                  onClick={() => setFilter(a.key)}
                  style={{
                    padding: 'var(--pad-3) var(--pad-4)',
                    borderBottom: '1px solid var(--border)',
                    cursor: 'pointer',
                    background: selectedKey === a.key ? 'var(--bg-2)' : 'transparent',
                    borderLeft: selectedKey === a.key
                      ? '2px solid var(--accent)'
                      : '2px solid transparent',
                    display: 'grid',
                    gridTemplateColumns: '1fr auto',
                    gap: 'var(--pad-2)',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div className="mono" style={{ fontSize: 13, color: 'var(--fg)' }}>
                      {a.model ?? '(no model)'}
                    </div>
                    <div className="muted mono" style={{ fontSize: 10 }}>
                      {a.role} · {Array.from(a.roles).join(', ')}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div className="num" style={{ color: 'var(--accent)' }}>{a.events}</div>
                    {a.fails > 0 && (
                      <div className="muted mono" style={{ fontSize: 10, color: 'var(--fail)' }}>
                        {a.fails} fail
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {byAgent.length === 0 && (
                <div style={{
                  padding: 'var(--pad-4)',
                  color: 'var(--fg-4)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  textAlign: 'center',
                }}>
                  No activity yet
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: detail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--pad-3)', padding: 'var(--pad-4)' }}>
          {selected ? (
            <>
              {/* KPI strip */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 1,
                background: 'var(--border)',
              }}>
                {([
                  ['Total events', String(selected.events)],
                  ['Roles',        Array.from(selected.roles).join(', ')],
                  ['QA fails',     String(selected.fails)],
                  ['Last seen',    relTime(selected.lastIso, selected.lastAge)],
                ] as [string, string][]).map(([k, v]) => (
                  <div key={k} style={{ background: 'var(--bg-1)', padding: 'var(--pad-3)' }}>
                    <div className="mono" style={{
                      fontSize: 10,
                      textTransform: 'uppercase',
                      letterSpacing: '.12em',
                      color: 'var(--fg-3)',
                      marginBottom: 4,
                    }}>{k}</div>
                    <div className="num" style={{ fontSize: 20, color: 'var(--fg)' }}>{v}</div>
                  </div>
                ))}
              </div>

              {/* Recent events */}
              <div className="panel">
                <div className="panel-h">
                  <span>Recent events for {selected.key}</span>
                  <span className="muted mono" style={{ fontSize: 10 }}>{selectedItems.length} shown</span>
                </div>
                <div style={{ overflow: 'auto', maxHeight: 480 }}>
                  {selectedItems.map(e => {
                    const glyph = EVENT_GLYPHS[e.event_type] ?? '·';
                    const color = glyphColor(e.event_type, e.role);
                    const ref = e.issue_number != null
                      ? `${e.project}#${e.issue_number}`
                      : e.pr_number != null
                        ? `${e.project}!${e.pr_number}`
                        : e.project;
                    return (
                      <div key={e.id} className="feed-row">
                        <span className="mono" style={{ color, fontSize: 12 }}>{glyph}</span>
                        <div>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <span className={`tag role-${e.role}`}>{e.role}</span>
                            <span className="mono" style={{ fontSize: 12 }}>{e.event_type}</span>
                            <span className="muted mono" style={{ fontSize: 11 }}>· {ref}</span>
                          </div>
                          {e.detail && (
                            <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{e.detail}</div>
                          )}
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div className="muted mono" style={{ fontSize: 10 }}>
                            {relTime(e.created_at, e.age_seconds)}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {selectedItems.length === 0 && (
                    <div style={{
                      padding: 'var(--pad-4)',
                      color: 'var(--fg-4)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 12,
                      textAlign: 'center',
                    }}>
                      No events for this agent
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div style={{
              padding: 'var(--pad-4)',
              color: 'var(--fg-3)',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
            }}>
              Select an agent from the list
            </div>
          )}
        </div>
      </div>
    </>
  );
}
