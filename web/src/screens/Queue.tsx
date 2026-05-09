import { useEffect, useState } from 'react';
import type { QueueItem } from '../lib/types';

function formatAge(seconds: number): string {
  if (seconds >= 3600) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  }
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

interface DrawerProps {
  item: QueueItem;
  onClose: () => void;
}

function Drawer({ item, onClose }: DrawerProps) {
  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={e => e.stopPropagation()}>
        <button className="drawer-close" onClick={onClose}>×</button>
        <h2>{item.title || `${item.kind} #${item.number}`}</h2>
        <dl>
          <dt>Project</dt><dd>{item.project}</dd>
          <dt>Stage</dt><dd>{item.stage}</dd>
          <dt>Age</dt><dd>{formatAge(item.age_seconds)}</dd>
          <dt>Reason</dt><dd>{item.reason}</dd>
          {item.threshold_seconds !== null && (
            <><dt>Threshold</dt><dd>{formatAge(item.threshold_seconds)}</dd></>
          )}
        </dl>
        {item.github_url && (
          <a href={item.github_url} target="_blank" rel="noreferrer">
            View on GitHub
          </a>
        )}
      </div>
    </div>
  );
}

interface RowProps {
  item: QueueItem;
  onClick: (item: QueueItem) => void;
}

function QueueRow({ item, onClick }: RowProps) {
  return (
    <tr className="queue-row" onClick={() => onClick(item)} style={{ cursor: 'pointer' }}>
      <td>{item.project}</td>
      <td>{item.kind} #{item.number}</td>
      <td>{item.stage}</td>
      <td>{formatAge(item.age_seconds)}</td>
      <td>{item.stage}</td>
    </tr>
  );
}

export default function Queue() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [selected, setSelected] = useState<QueueItem | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/action_queue')
      .then(r => r.json())
      .then((data: QueueItem[]) => {
        setItems(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const stuckItems = items
    .filter(i => i.reason === 'stuck_label' || i.reason === 'timeout')
    .sort((a, b) => b.age_seconds - a.age_seconds);

  const otherItems = items
    .filter(i => i.reason !== 'stuck_label' && i.reason !== 'timeout')
    .sort((a, b) => b.age_seconds - a.age_seconds);

  if (loading) return <div className="muted">Loading…</div>;

  return (
    <div className="queue-screen">
      <section className="queue-section">
        <h2 className="queue-section-title">Stuck</h2>
        {stuckItems.length === 0 ? (
          <div className="muted">No stuck items</div>
        ) : (
          <table className="queue-table">
            <thead>
              <tr>
                <th>Project</th>
                <th>Item</th>
                <th>Stage</th>
                <th>Age</th>
                <th>Last Event</th>
              </tr>
            </thead>
            <tbody>
              {stuckItems.map(item => (
                <QueueRow
                  key={`${item.project}-${item.kind}-${item.number}`}
                  item={item}
                  onClick={setSelected}
                />
              ))}
            </tbody>
          </table>
        )}
      </section>

      {otherItems.length > 0 && (
        <section className="queue-section">
          <h2 className="queue-section-title">Action Queue</h2>
          <table className="queue-table">
            <thead>
              <tr>
                <th>Project</th>
                <th>Item</th>
                <th>Stage</th>
                <th>Age</th>
                <th>Last Event</th>
              </tr>
            </thead>
            <tbody>
              {otherItems.map(item => (
                <QueueRow
                  key={`${item.project}-${item.kind}-${item.number}`}
                  item={item}
                  onClick={setSelected}
                />
              ))}
            </tbody>
          </table>
        </section>
      )}

      {selected && <Drawer item={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
