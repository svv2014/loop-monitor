import { useEffect, useState, useRef } from 'react';
import { fetchScannerState } from '../lib/api';
import type { ScannerState as ScannerStateType, RetryRow } from '../lib/types';

const ROLES = ['po', 'dev', 'qa', 'reviewer', 'merge'] as const;
const POLL_MS = 5000;

interface Props {
  projectId: string;
}

export default function ScannerState({ projectId }: Props) {
  const [data, setData] = useState<ScannerStateType | null>(null);
  const [error, setError] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const result = await fetchScannerState();
        if (!cancelled) {
          setData(result);
          setError(false);
        }
      } catch {
        if (!cancelled) setError(true);
      }
    }

    load();
    timerRef.current = setInterval(load, POLL_MS);

    return () => {
      cancelled = true;
      if (timerRef.current !== null) clearInterval(timerRef.current);
    };
  }, []);

  const allCapsNull = data
    ? ROLES.every((r) => data.stages[r]?.cap == null)
    : false;

  const projectRetries: RetryRow[] = data
    ? data.retries.filter((r) => r.project === projectId)
    : [];

  if (error && !data) {
    return (
      <div className="panel">
        <div className="panel-h">Scanner State</div>
        <div style={{ padding: 'var(--pad-3)', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
          Scanner state unavailable
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-h">Scanner State</div>

      <div style={{ padding: 'var(--pad-2) var(--pad-3)', borderBottom: 'var(--hairline) solid var(--border)' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--fg-3)', marginBottom: 'var(--pad-2)' }}>
          Global concurrency
        </div>
        {allCapsNull ? (
          <div style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            Scanner state unavailable
          </div>
        ) : (
          <table className="t">
            <thead>
              <tr>
                <th>Stage</th>
                <th>Used</th>
                <th>Cap</th>
                <th style={{ minWidth: 80 }}>Util</th>
              </tr>
            </thead>
            <tbody>
              {ROLES.map((role) => {
                const stage = data?.stages[role];
                const used = stage?.in_flight ?? 0;
                const cap = stage?.cap ?? null;
                const pct = cap != null && cap > 0 ? Math.round((used / cap) * 100) : null;
                return (
                  <tr key={role}>
                    <td>
                      <span className={`tag role-${role}`}>{role}</span>
                    </td>
                    <td className="num">{used}</td>
                    <td className="num">{cap ?? '—'}</td>
                    <td>
                      {pct != null ? (
                        <UtilBar pct={pct} />
                      ) : (
                        <span className="dim">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div style={{ padding: 'var(--pad-2) var(--pad-3)' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--fg-3)', marginBottom: 'var(--pad-2)' }}>
          Retries
        </div>
        {projectRetries.length === 0 ? (
          <div style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            No retries pending
          </div>
        ) : (
          <table className="t">
            <thead>
              <tr>
                <th>Project</th>
                <th>Ticket</th>
                <th>Stage</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {projectRetries.map((row, i) => (
                <tr key={i}>
                  <td className="mono">{row.project}</td>
                  <td className="mono">{row.kind}#{row.number}</td>
                  <td>
                    <span className={`tag role-${row.stage}`}>{row.stage}</span>
                  </td>
                  <td className="num">{row.count}/{row.max}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function UtilBar({ pct }: { pct: number }) {
  const color = pct >= 90
    ? 'var(--fail)'
    : pct >= 70
    ? 'var(--warn)'
    : 'var(--accent)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 4, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, transition: 'width 0.3s' }} />
      </div>
      <span className="num" style={{ fontSize: 10, color: 'var(--fg-3)', minWidth: 28, textAlign: 'right' }}>
        {pct}%
      </span>
    </div>
  );
}
