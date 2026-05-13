// TODO(#113): capture reference screenshot once visual-diff harness lands
import { useState } from 'react';
import { fetchLogs, LogsDisabledError } from '../lib/api';
import type { LogsResponse, LogLine } from '../lib/types';

const HANDLERS = [
  'scanner', 'reconciler', 'po-handler', 'dev-handler',
  'dev-rework-handler', 'review-handler', 'qa-handler', 'merge-handler',
];

function fmtBytes(n: number | null | undefined): string {
  if (n == null) return '?';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function LogLineRow({ line }: { line: LogLine }) {
  return (
    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: '1.6', padding: '1px 0' }}>
      {line.ts && <span style={{ color: 'var(--fg-3)' }}>{line.ts} </span>}
      {line.handler && <span style={{ color: 'var(--info)' }}>[{line.handler}] </span>}
      <span>{line.msg ?? line.raw ?? ''}</span>
    </div>
  );
}

export default function Logs() {
  const [handler, setHandler] = useState('scanner');
  const [filter, setFilter] = useState('');
  const [tail, setTail] = useState('200');
  const [data, setData] = useState<LogsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    setDisabled(false);
    try {
      const result = await fetchLogs(handler, filter, tail);
      setData(result);
    } catch (e) {
      setData(null);
      if (e instanceof LogsDisabledError) {
        setDisabled(true);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 'var(--pad-4)', display: 'flex', flexDirection: 'column', gap: 'var(--pad-3)', height: '100%', boxSizing: 'border-box' }}>
      <div className="screen-h" style={{ padding: 0, border: 'none' }}>
        <h1>Logs</h1>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--pad-2)', flexWrap: 'wrap' }}>
        <select
          value={handler}
          onChange={e => setHandler(e.target.value)}
          style={{
            fontFamily: 'var(--font-mono)', fontSize: 12, padding: '4px 8px',
            background: 'var(--bg-2)', color: 'var(--fg)', border: '1px solid var(--border)',
            borderRadius: 2, cursor: 'pointer',
          }}
        >
          {HANDLERS.map(h => <option key={h} value={h}>{h}</option>)}
        </select>

        <input
          type="text"
          placeholder="filter"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') refresh(); }}
          style={{
            fontFamily: 'var(--font-mono)', fontSize: 12, padding: '4px 8px',
            background: 'var(--bg-2)', color: 'var(--fg)', border: '1px solid var(--border)',
            borderRadius: 2, width: 180,
          }}
        />

        <input
          type="text"
          placeholder="tail"
          value={tail}
          onChange={e => setTail(e.target.value)}
          style={{
            fontFamily: 'var(--font-mono)', fontSize: 12, padding: '4px 8px',
            background: 'var(--bg-2)', color: 'var(--fg)', border: '1px solid var(--border)',
            borderRadius: 2, width: 70,
          }}
        />

        <button className="btn primary" onClick={refresh} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {data && (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)' }}>
          {data.path} · disk={fmtBytes(data.on_disk_bytes)} · fd={fmtBytes(data.fd_bytes)}
        </div>
      )}

      {data?.orphaned && (
        <div style={{
          background: 'var(--bg-2)',
          borderLeft: '3px solid var(--accent)',
          padding: 'var(--pad-3)',
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          color: 'var(--warn)',
        }}>
          WARNING: {handler} log appears orphaned (FD {fmtBytes(data.fd_bytes)}, file {fmtBytes(data.on_disk_bytes)}). The handler may have rotated or replaced its log file while the dashboard kept reading the old descriptor — restart the handler to re-attach.
        </div>
      )}

      {disabled && (
        <div style={{ color: 'var(--role-err)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
          Logs are disabled. Set LOOPMON_EXPOSE_LOGS=1 or access via loopback.
        </div>
      )}

      {error && (
        <div style={{ color: 'var(--role-err)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
          Error: {error}
        </div>
      )}

      {data && (
        <div style={{
          flex: 1, overflow: 'auto',
          background: 'var(--bg-1)', border: '1px solid var(--border)',
          padding: 'var(--pad-3)',
          minHeight: 0,
        }}>
          {data.lines.length === 0
            ? <div style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>No matching lines.</div>
            : data.lines.map((line, i) => <LogLineRow key={i} line={line} />)
          }
        </div>
      )}

      {!data && !disabled && !error && !loading && (
        <div style={{ color: 'var(--fg-4)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
          Select a handler and click Refresh to load logs.
        </div>
      )}
    </div>
  );
}
