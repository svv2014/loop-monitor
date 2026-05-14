import { useState } from 'react';
import type { CostTimeseriesBucket } from '../lib/types';

interface CostTimeseriesProps {
  buckets: CostTimeseriesBucket[];
  activeDayHash: string | null;
  onDayClick: (date: string) => void;
}

// Stage order and matching role CSS tokens
const STAGES: { key: keyof CostTimeseriesBucket['by_stage']; label: string; cssVar: string }[] = [
  { key: 'po_failed',     label: 'PO Failed',      cssVar: 'var(--role-po)' },
  { key: 'dev_rework',    label: 'Dev Rework',     cssVar: 'var(--role-dev)' },
  { key: 'qa_fail',       label: 'QA Fail',        cssVar: 'var(--role-qa)' },
  { key: 'review_reject', label: 'Review Reject',  cssVar: 'var(--role-reviewer)' },
];

interface TooltipState {
  bucket: CostTimeseriesBucket;
  x: number;
  y: number;
}

export default function CostTimeseries({ buckets, activeDayHash, onDayClick }: CostTimeseriesProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const max = Math.max(1, ...buckets.map(b => b.total_rework_events));

  return (
    <div className="panel">
      <div className="panel-h">
        <span>Rework events — last {buckets.length}d</span>
        <span className="muted">
          {STAGES.map(s => (
            <span key={s.key} style={{ marginLeft: 12 }}>
              <span style={{
                display: 'inline-block',
                width: 8,
                height: 8,
                marginRight: 4,
                verticalAlign: 'middle',
                background: s.cssVar,
              }} />
              {s.label}
            </span>
          ))}
        </span>
      </div>

      <div style={{ position: 'relative', height: 130, padding: 'var(--pad-3) 0 var(--pad-4)' }}>
        <div
          className="bars"
          onMouseLeave={() => setTooltip(null)}
        >
          {buckets.map((b, i) => {
            const isActive = activeDayHash === b.date;
            return (
              <div
                key={b.date}
                className="bar-col"
                style={{ cursor: 'pointer', outline: isActive ? `1px solid var(--border-strong)` : undefined }}
                onClick={() => onDayClick(b.date)}
                onMouseEnter={e => {
                  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
                  setTooltip({ bucket: b, x: rect.left + rect.width / 2, y: rect.top });
                }}
              >
                {STAGES.map(s => {
                  const v = b.by_stage[s.key] ?? 0;
                  if (!v) return null;
                  return (
                    <div
                      key={s.key}
                      className="bar-seg"
                      style={{
                        background: s.cssVar,
                        height: `${(v / max) * 100}%`,
                        opacity: isActive ? 1 : 0.85,
                      }}
                    />
                  );
                })}
                {(i % 5 === 0) && (
                  <div className="bar-tick">{b.date.slice(5)}</div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {tooltip && (
        <div
          style={{
            position: 'fixed',
            left: tooltip.x,
            top: tooltip.y - 8,
            transform: 'translate(-50%, -100%)',
            background: 'var(--bg-3)',
            border: '1px solid var(--border-strong)',
            padding: 'var(--pad-2) var(--pad-3)',
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--fg)',
            zIndex: 200,
            pointerEvents: 'none',
            minWidth: 160,
          }}
        >
          <div style={{ marginBottom: 4, color: 'var(--fg-2)', letterSpacing: '0.06em' }}>
            {tooltip.bucket.date}
          </div>
          <div style={{ marginBottom: 6, fontSize: 13, fontWeight: 600 }}>
            {tooltip.bucket.total_rework_events} rework events
          </div>
          {STAGES.map(s => {
            const v = tooltip.bucket.by_stage[s.key];
            if (!v) return null;
            return (
              <div key={s.key} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 2 }}>
                <span style={{ color: s.cssVar }}>{s.label}</span>
                <span className="num">{v}</span>
              </div>
            );
          })}
          {tooltip.bucket.top_issues.length > 0 && (
            <>
              <div style={{ borderTop: '1px solid var(--border)', margin: '6px 0 4px', color: 'var(--fg-4)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                top issues
              </div>
              {tooltip.bucket.top_issues.map(ti => (
                <div key={ti.issue_number} style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
                  <span style={{ color: 'var(--fg-3)' }}>#{ti.issue_number}</span>
                  <span className="num">{ti.count}</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
