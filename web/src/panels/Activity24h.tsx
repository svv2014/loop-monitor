import type { HourBucket } from '../lib/transforms';

const ROLE_ORDER = ['po', 'dev', 'qa', 'reviewer', 'merge', 'judge'] as const;

interface Activity24hProps {
  buckets: HourBucket[];
}

export default function Activity24h({ buckets }: Activity24hProps) {
  const max = Math.max(1, ...buckets.map(b => b.total));

  return (
    <div className="panel">
      <div className="panel-h">
        <span>24h pipeline activity</span>
        <span className="muted">
          {ROLE_ORDER.map(r => (
            <span key={r} style={{ marginLeft: 12 }}>
              <span style={{
                display: 'inline-block',
                width: 8,
                height: 8,
                marginRight: 4,
                verticalAlign: 'middle',
                background: `var(--role-${r})`,
              }}></span>{r}
            </span>
          ))}
        </span>
      </div>
      <div style={{ position: 'relative', height: 130, padding: '14px 0 24px' }}>
        <div className="bars">
          {buckets.map((b, i) => (
            <div key={i} className="bar-col">
              {ROLE_ORDER.map(r => {
                const v = b.counts[r] ?? 0;
                if (!v) return null;
                return (
                  <div
                    key={r}
                    className="bar-seg"
                    style={{
                      background: `var(--role-${r})`,
                      height: `${(v / max) * 100}%`,
                    }}
                  />
                );
              })}
              {(i % 6 === 0) && (
                <div className="bar-tick">{String(b.hour).padStart(2, '0')}:00</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
