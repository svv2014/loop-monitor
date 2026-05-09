import { useEffect, useRef, useState } from 'react';
import { fetchFailureContext } from '../lib/api';
import type { FailureContext } from '../lib/types';

interface Props {
  project: string;
  kind: string;
  number: number;
  title: string;
  onClose: () => void;
}

function useFailureContext(project: string, kind: string, number: number) {
  const [data, setData] = useState<FailureContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetched = useRef(false);

  useEffect(() => {
    if (fetched.current) return;
    fetched.current = true;
    fetchFailureContext(project, kind, number)
      .then(setData)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [project, kind, number]);

  return { data, loading, error };
}

function copyToClipboard(text: string) {
  if (typeof navigator !== 'undefined' && navigator.clipboard) {
    navigator.clipboard.writeText(text).catch(() => _fallbackCopy(text));
  } else {
    _fallbackCopy(text);
  }
}

function _fallbackCopy(text: string) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try { document.execCommand('copy'); } catch { /* ignore */ }
  document.body.removeChild(ta);
}

function fmtTs(ts: string): string {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toISOString().replace('T', ' ').slice(0, 19);
  } catch {
    return ts;
  }
}

export default function FailureInspector({ project, kind, number, title, onClose }: Props) {
  const { data, loading, error } = useFailureContext(project, kind, number);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (data?.excerpt) {
      copyToClipboard(data.excerpt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="drawer-overlay" onClick={handleOverlayClick}>
      <aside className="drawer">
        <div className="drawer-h">
          <div className="drawer-h-left">
            <span className="drawer-kind mono">{kind} #{number}</span>
            <span className="drawer-title">{title}</span>
          </div>
          <button className="btn drawer-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="drawer-body">
          {loading && <p className="muted mono" style={{ padding: 'var(--pad-3)' }}>Loading…</p>}
          {error && <p className="drawer-err">{error}</p>}

          {!loading && !error && data && (
            <>
              <div className="drawer-meta">
                <MetaRow label="stage">
                  <span className="tag" style={{ color: 'var(--fail)' }}>failure</span>
                </MetaRow>
                <MetaRow label="retry">{data.retry_count}</MetaRow>
                <MetaRow label="model">{data.model ?? '—'}</MetaRow>
                <MetaRow label="run id">{data.run_id ?? '—'}</MetaRow>
                <MetaRow label="timestamp">{fmtTs(data.timestamp)}</MetaRow>
                {data.github_url && (
                  <MetaRow label="issue">
                    <a className="drawer-link" href={data.github_url} target="_blank" rel="noopener noreferrer">
                      {data.github_url}
                    </a>
                  </MetaRow>
                )}
                {data.github_comment_url && (
                  <MetaRow label="comment">
                    <a className="drawer-link" href={data.github_comment_url} target="_blank" rel="noopener noreferrer">
                      view comment ↗
                    </a>
                  </MetaRow>
                )}
                {data.log_path && (
                  <MetaRow label="log path">
                    <span className="mono dim">{data.log_path}</span>
                  </MetaRow>
                )}
              </div>

              <div className="drawer-excerpt-h panel-h">
                <span>error excerpt</span>
                {data.excerpt && (
                  <button className="btn" onClick={handleCopy}>
                    {copied ? 'copied' : 'copy'}
                  </button>
                )}
              </div>

              <div className="drawer-excerpt-wrap">
                {data.excerpt ? (
                  <pre className="drawer-excerpt">{data.excerpt}</pre>
                ) : (
                  <p className="drawer-empty muted">
                    {data.log_path
                      ? <>No failure context yet — see log file at <span className="mono dim">{data.log_path}</span></>
                      : 'No failure context available.'}
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="drawer-meta-row">
      <span className="drawer-meta-label">{label}</span>
      <span className="drawer-meta-value mono">{children}</span>
    </div>
  );
}
