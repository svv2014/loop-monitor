import Velocity from '../panels/Velocity';

export default function Analytics() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--pad-3)', padding: 'var(--pad-3)' }}>
      {/* velocity slot */}
      <Velocity />
    </div>
  );
}
