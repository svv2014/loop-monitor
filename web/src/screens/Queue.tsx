import { useEffect, useState } from 'react';
import FailureInspector from '../components/FailureInspector';
import { fetchActionQueue } from '../lib/api';
import type { ActionQueueItem } from '../lib/types';

const FAILURE_REASONS = new Set(['needs-clarification', 'stuck_label', 'qa_fail_repeated']);

function ageLabel(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

interface SelectedItem {
  project: string;
  kind: string;
  number: number;
  title: string;
}

export default function Queue() {
  const [items, setItems] = useState<ActionQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<SelectedItem | null>(null);

  useEffect(() => {
    fetchActionQueue()
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  const handleRowClick = (item: ActionQueueItem) => {
    if (FAILURE_REASONS.has(item.reason) || FAILURE_REASONS.has(item.stage)) {
      setSelected({ project: item.project, kind: item.kind, number: item.number, title: item.title });
    }
  };

  return (
    <div className="queue-screen">
      <div className="screen-h">
        <h1>Action Queue</h1>
        <span className="meta">{items.length} items</span>
      </div>

      <div className="panel" style={{ margin: 'var(--pad-3)', marginTop: 0 }}>
        {loading && <p className="muted" style={{ padding: 'var(--pad-3)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>Loading…</p>}
        {!loading && items.length === 0 && (
          <p className="muted" style={{ padding: 'var(--pad-3)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>Queue is empty.</p>
        )}
        {!loading && items.length > 0 && (
          <table className="t">
            <thead>
              <tr>
                <th>project</th>
                <th>#</th>
                <th>title</th>
                <th>stage</th>
                <th>reason</th>
                <th>age</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const clickable = FAILURE_REASONS.has(item.reason) || FAILURE_REASONS.has(item.stage);
                return (
                  <tr
                    key={`${item.project}-${item.kind}-${item.number}`}
                    onClick={clickable ? () => handleRowClick(item) : undefined}
                    className={clickable ? 'queue-row queue-row--clickable' : 'queue-row'}
                  >
                    <td className="mono dim">{item.project}</td>
                    <td className="mono">
                      {item.github_url ? (
                        <a className="drawer-link" href={item.github_url} target="_blank" rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}>
                          {item.kind} #{item.number}
                        </a>
                      ) : (
                        <>{item.kind} #{item.number}</>
                      )}
                    </td>
                    <td>{item.title}</td>
                    <td>
                      <span className="tag">{item.stage}</span>
                    </td>
                    <td>
                      <ReasonPill reason={item.reason} />
                    </td>
                    <td className="mono num dim">{ageLabel(item.age_seconds)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <FailureInspector
          project={selected.project}
          kind={selected.kind}
          number={selected.number}
          title={selected.title}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function ReasonPill({ reason }: { reason: string }) {
  const color = reason === 'qa_fail_repeated' ? 'var(--warn)' : 'var(--fail)';
  return <span className="tag" style={{ color }}>{reason}</span>;
}
