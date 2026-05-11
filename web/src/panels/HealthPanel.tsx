import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchPipelineHealth } from '../lib/api';
import type { SubsystemHealth } from '../lib/types';
import { relTime } from '../lib/utils';

const STATUS_COLOR: Record<string, string> = {
  ok:    'var(--pass)',
  stale: 'var(--warn)',
  down:  'var(--fail)',
};

function StatusPill({ status }: { status: 'ok' | 'stale' | 'down' }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 7px',
      borderRadius: 3,
      fontSize: 10,
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
      color: STATUS_COLOR[status],
      border: `1px solid ${STATUS_COLOR[status]}`,
      lineHeight: '18px',
    }}>
      {status}
    </span>
  );
}

function SubsystemRow({
  name,
  sub,
  onClick,
}: {
  name: string;
  sub: SubsystemHealth;
  onClick: () => void;
}) {
  const lastTick = sub.last_tick_iso ? relTime(new Date(sub.last_tick_iso).getTime()) : null;

  return (
    <button
      onClick={onClick}
      style={{
        all: 'unset',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--pad-3)',
        padding: 'var(--pad-2) var(--pad-3)',
        cursor: 'pointer',
        width: '100%',
        boxSizing: 'border-box',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        color: 'var(--fg)',
        flex: '0 0 120px',
      }}>
        {name}
      </span>
      <StatusPill status={sub.status} />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)' }}>
        {lastTick ? `last tick: ${lastTick}` : 'no data'}
      </span>
    </button>
  );
}

function DetailDrawer({ name, sub, onClose }: { name: string; sub: SubsystemHealth; onClose: () => void }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'oklch(0 0 0 / 0.5)',
        zIndex: 200,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        onClick={e => e.stopPropagation()}
        onKeyDown={e => e.key === 'Escape' && onClose()}
        style={{
          width: 360,
          height: '100%',
          background: 'var(--bg-2)',
          borderLeft: '1px solid var(--border)',
          padding: 'var(--pad-4)',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--pad-3)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--fg)' }}>
            {name}
          </h2>
          <button className="btn" onClick={onClose}>×</button>
        </div>
        <div>
          <StatusPill status={sub.status} />
        </div>
        {sub.last_tick_iso && (
          <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', fontSize: 12 }}>
            <dt style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>last tick</dt>
            <dd style={{ margin: 0, color: 'var(--fg)', fontFamily: 'var(--font-mono)' }}>
              {relTime(new Date(sub.last_tick_iso).getTime())}
            </dd>
            {sub.interval_seconds != null && (
              <>
                <dt style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>interval</dt>
                <dd style={{ margin: 0, color: 'var(--fg)', fontFamily: 'var(--font-mono)' }}>
                  {sub.interval_seconds}s
                </dd>
              </>
            )}
          </dl>
        )}
        {sub.detail && (
          <div style={{
            background: 'var(--bg-3)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            padding: 'var(--pad-2)',
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--fg-2)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
            {sub.detail}
          </div>
        )}
        <p style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', margin: 0 }}>
          To restart: <code>launchctl kickstart -k gui/$(id -u)/com.loop.{name.toLowerCase()}</code>
        </p>
      </div>
    </div>
  );
}

export default function HealthPanel() {
  const [open, setOpen] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ['pipelineHealth'],
    queryFn: fetchPipelineHealth,
    refetchInterval: 30_000,
    staleTime: 0,
  });

  const subsystems: Array<{ key: string; label: string }> = [
    { key: 'scanner',      label: 'scanner' },
    { key: 'orchestrator', label: 'orchestrator' },
    { key: 'event_queue',  label: 'event-queue' },
  ];

  return (
    <div className="panel">
      <div className="panel-h">
        <span>Pipeline health</span>
      </div>
      {data ? (
        subsystems.map(({ key, label }) => {
          const sub = data[key as keyof typeof data];
          return (
            <SubsystemRow
              key={key}
              name={label}
              sub={sub}
              onClick={() => setOpen(key)}
            />
          );
        })
      ) : (
        <div style={{ padding: 'var(--pad-3)', fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
          loading…
        </div>
      )}

      {open && data && (() => {
        const sub = data[open as keyof typeof data];
        const label = subsystems.find(s => s.key === open)?.label ?? open;
        return (
          <DetailDrawer
            name={label}
            sub={sub}
            onClose={() => setOpen(null)}
          />
        );
      })()}
    </div>
  );
}
