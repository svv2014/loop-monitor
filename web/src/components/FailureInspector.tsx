import { useState } from 'react';
import Drawer from './Drawer';
import { useHashRoute } from '../router';

export interface FailureItem {
  project: string;
  kind: string;
  number: number;
  title?: string;
  excerpt?: string;
  github_url?: string;
}

function itemDrawerKey(item: FailureItem): string {
  return `item:${item.project}:${item.kind}:${item.number}`;
}

interface FailureInspectorProps {
  item: FailureItem | null;
}

export default function FailureInspector({ item }: FailureInspectorProps) {
  const { drawer, setHash } = useHashRoute();
  const [copied, setCopied] = useState(false);

  const open = item !== null && drawer === itemDrawerKey(item);

  function closeDrawer() {
    setHash({ drawer: undefined });
  }

  function copyExcerpt() {
    if (!item?.excerpt) return;
    navigator.clipboard.writeText(item.excerpt).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <Drawer
      open={open}
      onClose={closeDrawer}
      title={item ? `${item.kind} #${item.number}` : undefined}
    >
      {item && (
        <div className="failure-inspector">
          {item.title && <h3 style={{ margin: '0 0 var(--pad-3)' }}>{item.title}</h3>}
          {item.excerpt && (
            <div style={{ marginBottom: 'var(--pad-3)' }}>
              <pre
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  background: 'var(--bg-3)',
                  padding: 'var(--pad-3)',
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                }}
              >
                {item.excerpt}
              </pre>
              <button className="btn" onClick={copyExcerpt}>
                {copied ? 'Copied!' : 'Copy excerpt'}
              </button>
            </div>
          )}
          {item.github_url && (
            <a href={item.github_url} target="_blank" rel="noreferrer">
              View on GitHub
            </a>
          )}
        </div>
      )}
    </Drawer>
  );
}
