import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchPipelineHealth } from '../lib/api';
import { getFixturePipelineHealth } from '../lib/fixtures';
import type { SubsystemHealth, SubsystemStatus, PipelineHealth } from '../lib/types';

const FIXTURE_MODE = new URLSearchParams(window.location.search).get('fixtures') === '1';

function relativeTime(isoStr: string | null): string {
  if (!isoStr) return 'never';
  const delta = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (delta < 60) return `${delta}s ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  return `${Math.floor(delta / 3600)}h ago`;
}

const STATUS_COLOR: Record<SubsystemStatus, string> = {
  ok: 'var(--pass)',
  stale: 'var(--warn)',
  down: 'var(--fail)',
};

interface RowProps {
  label: string;
  sub: SubsystemHealth;
  open: boolean;
  onToggle: () => void;
}

function HealthRow({ label, sub, open, onToggle }: RowProps) {
  const color = STATUS_COLOR[sub.status];
  return (
    <div style={{ borderBottom: '1px solid var(--border)' }}>
      <button
        onClick={onToggle}
        style={{
          width: '100%',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--pad-2)',
          padding: 'var(--pad-2) var(--pad-3)',
          textAlign: 'left',
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--fg-2)',
            minWidth: 110,
          }}
        >
          {label}
        </span>
        <span
          style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: 11,
            fontWeight: 600,
            fontFamily: 'var(--font-mono)',
            background: color,
            color: 'var(--bg)',
          }}
        >
          {sub.status}
        </span>
        <span style={{ fontSize: 12, color: 'var(--fg-4)', marginLeft: 'auto' }}>
          last tick: {relativeTime(sub.last_tick_iso)}
        </span>
        <span style={{ fontSize: 10, color: 'var(--fg-4)', marginLeft: 'var(--pad-1)' }}>
          {open ? '▲' : '▼'}
        </span>
      </button>

      {open && (
        <div
          style={{
            padding: 'var(--pad-2) var(--pad-3) var(--pad-3)',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--fg-3)',
            background: 'var(--bg-1)',
            borderTop: '1px solid var(--border)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {sub.detail || '(no detail)'}
        </div>
      )}
    </div>
  );
}

export default function HealthPanel() {
  const [openRow, setOpenRow] = useState<string | null>(null);

  const { data, isError } = useQuery<PipelineHealth>({
    queryKey: ['pipeline-health'],
    queryFn: FIXTURE_MODE ? getFixturePipelineHealth : fetchPipelineHealth,
    refetchInterval: 30_000,
  });

  const toggle = (key: string) => setOpenRow(prev => (prev === key ? null : key));

  const LABELS: [keyof PipelineHealth, string][] = [
    ['scanner', 'scanner'],
    ['orchestrator', 'orchestrator'],
    ['event_queue', 'event-queue'],
  ];

  return (
    <div
      style={{
        background: 'var(--bg-2)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: 'var(--pad-2) var(--pad-3)',
          borderBottom: '1px solid var(--border)',
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--fg-3)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        }}
      >
        Pipeline Health
      </div>

      {isError && (
        <div style={{ padding: 'var(--pad-2) var(--pad-3)', color: 'var(--fail)', fontSize: 12 }}>
          Failed to load pipeline health
        </div>
      )}

      {data && LABELS.map(([key, label]) => (
        <HealthRow
          key={key}
          label={label}
          sub={data[key]}
          open={openRow === key}
          onToggle={() => toggle(key)}
        />
      ))}

      {!data && !isError && (
        <div style={{ padding: 'var(--pad-2) var(--pad-3)', color: 'var(--fg-4)', fontSize: 12 }}>
          Loading…
        </div>
      )}
    </div>
  );
}
