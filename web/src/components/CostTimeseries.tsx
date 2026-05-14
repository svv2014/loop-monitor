import { useState } from 'react';
import type { CostTimeseriesBucket } from '../lib/types';

interface CostTimeseriesProps {
  buckets: CostTimeseriesBucket[];
  selectedDay: string | null;
  onDayClick: (date: string | null) => void;
}

const STAGES = [
  { key: 'po_failed'     as const, label: 'PO',     color: 'var(--role-po)' },
  { key: 'dev_rework'    as const, label: 'Dev',     color: 'var(--role-dev)' },
  { key: 'qa_fail'       as const, label: 'QA',      color: 'var(--role-qa)' },
  { key: 'review_reject' as const, label: 'Review',  color: 'var(--role-reviewer)' },
] as const;

interface TooltipState {
  bucket: CostTimeseriesBucket;
  x: number;
  y: number;
}

export default function CostTimeseries({ buckets, selectedDay, onDayClick }: CostTimeseriesProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const max = Math.max(1, ...buckets.map(b => b.total_rework_events));

  function handleBarClick(b: CostTimeseriesBucket) {
    onDayClick(selectedDay === b.date ? null : b.date);
  }

  function handleMouseEnter(e: React.MouseEvent, b: CostTimeseriesBucket) {
    const rect = (e.currentTarget as HTMLElement).closest('.bars')!.getBoundingClientRect();
    const colRect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setTooltip({
      bucket: b,
      x: colRect.left - rect.left + colRect.width / 2,
      y: 0,
    });
  }

  function handleMouseLeave() {
    setTooltip(null);
  }

  return (
    <div className="panel" style={{ borderTop: '1px solid var(--border)' }}>
      <div className="panel-h">
        <span>Rework events — last {buckets.length} days</span>
        <span className="muted">
          {STAGES.map(s => (
            <span key={s.key} style={{ marginLeft: 12 }}>
              <span style={{
                display: 'inline-block',
                width: 8,
                height: 8,
                marginRight: 4,
                verticalAlign: 'middle',
                background: s.color,
              }} />
              {s.label}
            </span>
          ))}
          {selectedDay && (
            <button
              className="btn"
              onClick={() => onDayClick(null)}
              style={{ marginLeft: 12, fontSize: 9, padding: '2px 6px' }}
            >
              Clear {selectedDay}
            </button>
          )}
        </span>
      </div>
      <div style={{ position: 'relative', height: 130, padding: '14px 0 24px' }}>
        <div className="bars" style={{ position: 'relative' }}>
          {buckets.map((b, i) => {
            const isSelected = selectedDay === b.date;
            const hasData = b.total_rework_events > 0;
            return (
              <div
                key={b.date}
                className="bar-col"
                onClick={() => hasData && handleBarClick(b)}
                onMouseEnter={e => hasData && handleMouseEnter(e, b)}
                onMouseLeave={handleMouseLeave}
                style={{
                  cursor: hasData ? 'pointer' : 'default',
                  opacity: selectedDay && !isSelected ? 0.4 : 1,
                  outline: isSelected ? '1px solid var(--accent)' : 'none',
                  outlineOffset: '2px',
                  transition: 'opacity .15s',
                }}
              >
                {STAGES.map(s => {
                  const v = b.by_stage[s.key];
                  if (!v) return null;
                  return (
                    <div
                      key={s.key}
                      className="bar-seg"
                      style={{
                        background: s.color,
                        height: `${(v / max) * 100}%`,
                      }}
                    />
                  );
                })}
                {i % 7 === 0 && (
                  <div className="bar-tick">{b.date.slice(5)}</div>
                )}
              </div>
            );
          })}
          {tooltip && (
            <div
              style={{
                position: 'absolute',
                left: tooltip.x,
                top: 4,
                transform: 'translateX(-50%)',
                background: 'var(--bg-3)',
                border: '1px solid var(--border-strong)',
                padding: '8px 10px',
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                whiteSpace: 'nowrap',
                zIndex: 10,
                pointerEvents: 'none',
              }}
            >
              <div style={{ color: 'var(--fg)', marginBottom: 4 }}>
                {tooltip.bucket.date} — {tooltip.bucket.total_rework_events} events
              </div>
              {STAGES.filter(s => tooltip.bucket.by_stage[s.key] > 0).map(s => (
                <div key={s.key} style={{ color: s.color }}>
                  {s.label}: {tooltip.bucket.by_stage[s.key]}
                </div>
              ))}
              {tooltip.bucket.top_issues.length > 0 && (
                <>
                  <div style={{ color: 'var(--fg-3)', marginTop: 4, marginBottom: 2 }}>top issues</div>
                  {tooltip.bucket.top_issues.map(t => (
                    <div key={`${t.project}-${t.issue_number}`} style={{ color: 'var(--fg-2)' }}>
                      {t.project}#{t.issue_number} ({t.rework_events})
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
