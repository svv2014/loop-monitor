import { useEffect, useState } from 'react';
import type { QueueItem } from '../lib/types';
import Drawer from '../components/Drawer';
import { useHashRoute } from '../router';

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

function itemDrawerKey(item: QueueItem): string {
  return `item:${item.project}:${item.kind}:${item.number}`;
}

interface DrawerContentProps {
  item: QueueItem;
}

function QueueDrawerContent({ item }: DrawerContentProps) {
  return (
    <dl>
      <dt>Project</dt><dd>{item.project}</dd>
      <dt>Stage</dt><dd>{item.stage}</dd>
      <dt>Age</dt><dd>{formatAge(item.age_seconds)}</dd>
      <dt>Reason</dt><dd>{item.reason}</dd>
      {item.threshold_seconds !== null && (
        <><dt>Threshold</dt><dd>{formatAge(item.threshold_seconds)}</dd></>
      )}
      {item.github_url && (
        <dd>
          <a href={item.github_url} target="_blank" rel="noreferrer">
            View on GitHub
          </a>
        </dd>
      )}
    </dl>
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
  const [loading, setLoading] = useState(true);
  const { drawer, setHash } = useHashRoute();

  useEffect(() => {
    fetch('/api/action_queue')
      .then(r => r.json())
      .then((data: QueueItem[]) => {
        setItems(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const selected = items.find(i => itemDrawerKey(i) === drawer) ?? null;

  function openDrawer(item: QueueItem) {
    setHash({ drawer: itemDrawerKey(item) });
  }

  function closeDrawer() {
    setHash({ drawer: undefined });
  }

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
                  onClick={openDrawer}
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
                  onClick={openDrawer}
                />
              ))}
            </tbody>
          </table>
        </section>
      )}

      <Drawer
        open={selected !== null}
        onClose={closeDrawer}
        title={selected ? `${selected.kind} #${selected.number}` : undefined}
      >
        {selected && <QueueDrawerContent item={selected} />}
      </Drawer>
    </div>
  );
}
