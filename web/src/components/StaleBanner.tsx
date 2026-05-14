import { useState } from 'react';

interface StaleBannerProps {
  runningSha: string;
  latestSha: string;
}

export default function StaleBanner({ runningSha, latestSha }: StaleBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div
      style={{
        gridArea: 'topbar',
        marginTop: 'var(--topbar-h, 36px)',
        background: 'var(--amber, #d97706)',
        color: '#fff',
        padding: '4px 12px',
        fontSize: 12,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        zIndex: 10,
        position: 'relative',
      }}
    >
      <span className="mono" style={{ flex: 1 }}>
        Running <strong>{runningSha}</strong> — main is at <strong>{latestSha}</strong>. Run{' '}
        <code>scripts/redeploy.sh</code> to update.
      </span>
      <button
        onClick={() => setDismissed(true)}
        style={{
          background: 'transparent',
          border: '1px solid rgba(255,255,255,0.5)',
          color: '#fff',
          borderRadius: 3,
          padding: '1px 8px',
          cursor: 'pointer',
          fontSize: 11,
        }}
      >
        dismiss
      </button>
    </div>
  );
}
