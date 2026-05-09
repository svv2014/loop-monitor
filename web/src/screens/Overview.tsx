import HealthPanel from '../panels/HealthPanel';

export default function Overview() {
  return (
    <div style={{ display: 'flex', gap: 'var(--pad-4)', padding: 'var(--pad-4)', height: '100%' }}>
      <div style={{ flex: 1 }}>
        {/* main content area — future panels mount here */}
      </div>
      <div style={{ width: 320, flexShrink: 0 }}>
        <HealthPanel />
      </div>
    </div>
  );
}
