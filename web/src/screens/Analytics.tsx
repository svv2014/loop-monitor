import CycleTimePanel from '../panels/CycleTime';

export default function Analytics() {
  return (
    <div>
      <div className="screen-h">
        <h1>Analytics</h1>
      </div>
      <div style={{ padding: 'var(--pad-4)', display: 'grid', gap: 'var(--pad-3)' }}>
        <CycleTimePanel days={30} />
      </div>
    </div>
  );
}
