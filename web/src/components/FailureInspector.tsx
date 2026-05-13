import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchFailureContext } from '../lib/api';
import type { FailureContext } from '../lib/types';
import Drawer from './Drawer';

interface Props {
  project: string;
  kind: string;
  number: number;
  title: string;
  githubUrl: string | null;
  onClose: () => void;
}

async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
}

const DT_STYLE: React.CSSProperties = {
  color: 'var(--fg-3)',
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  alignSelf: 'center',
};

export default function FailureInspector({ project, kind, number, title, githubUrl, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['failure', project, kind, number],
    queryFn: () => fetchFailureContext(project, kind, number),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  async function handleCopy() {
    if (!data?.excerpt) return;
    await copyToClipboard(data.excerpt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Drawer open={true} onClose={onClose} title={title || `${kind} #${number}`}>
      {/* Metadata */}
      <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px var(--pad-3)', fontSize: 12 }}>
        <dt style={DT_STYLE}>Project</dt>
        <dd style={{ margin: 0 }}>{project}</dd>
        <dt style={DT_STYLE}>Item</dt>
        <dd style={{ margin: 0 }} className="mono">{kind} #{number}</dd>
      </dl>

      <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: 0 }} />

      {/* Failure context */}
      {isLoading ? (
        <div className="muted" style={{ fontSize: 12 }}>Loading failure context…</div>
      ) : !data || data.excerpt === null ? (
        <EmptyState logPath={data?.log_path ?? null} />
      ) : (
        <FailureDetail data={{ ...data, excerpt: data.excerpt }} copied={copied} onCopy={handleCopy} />
      )}

      {/* GitHub link */}
      {githubUrl && (
        <a
          href={githubUrl}
          target="_blank"
          rel="noreferrer"
          className="btn primary"
          style={{ display: 'inline-block', textAlign: 'center', textDecoration: 'none' }}
        >
          View on GitHub
        </a>
      )}
    </Drawer>
  );
}

function EmptyState({ logPath }: { logPath: string | null }) {
  return (
    <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
      {logPath
        ? <>No failure context yet — see log file at <span className="mono" style={{ color: 'var(--fg-2)' }}>{logPath}</span></>
        : 'No failure context available.'}
    </div>
  );
}

interface FailureDetailProps {
  data: FailureContext & { excerpt: string };
  copied: boolean;
  onCopy: () => void;
}

function FailureDetail({ data, copied, onCopy }: FailureDetailProps) {
  return (
    <>
      {/* Excerpt */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--pad-2)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--fg-3)' }}>
            Error Excerpt
          </span>
          <button
            className="btn"
            onClick={onCopy}
            style={{ fontSize: 11 }}
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
        <pre
          style={{
            margin: 0,
            padding: 'var(--pad-3)',
            background: 'var(--bg-1)',
            border: '1px solid var(--border)',
            borderRadius: 2,
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--fg-fail, var(--fg))',
            overflowY: 'auto',
            maxHeight: '50vh',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          {data.excerpt}
        </pre>
      </div>

      {/* Metadata grid */}
      <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px var(--pad-3)', fontSize: 12 }}>
        {data.retry_count > 0 && (
          <>
            <dt style={DT_STYLE}>Retries</dt>
            <dd style={{ margin: 0 }} className="num">{data.retry_count}</dd>
          </>
        )}
        {data.model && (
          <>
            <dt style={DT_STYLE}>Model</dt>
            <dd style={{ margin: 0 }} className="mono">{data.model}</dd>
          </>
        )}
        {data.run_id && (
          <>
            <dt style={DT_STYLE}>Run ID</dt>
            <dd style={{ margin: 0 }} className="mono">{data.run_id}</dd>
          </>
        )}
        {data.timestamp && (
          <>
            <dt style={DT_STYLE}>Time</dt>
            <dd style={{ margin: 0 }} className="mono">{data.timestamp}</dd>
          </>
        )}
        {data.log_path && (
          <>
            <dt style={DT_STYLE}>Log path</dt>
            <dd style={{ margin: 0, wordBreak: 'break-all' }} className="mono">{data.log_path}</dd>
          </>
        )}
      </dl>

      {/* Link to failure comment */}
      {data.github_comment_url && (
        <a
          href={data.github_comment_url}
          target="_blank"
          rel="noreferrer"
          className="btn"
          style={{ display: 'inline-block', textAlign: 'center', textDecoration: 'none', fontSize: 12 }}
        >
          View failure comment on GitHub
        </a>
      )}
    </>
  );
}
