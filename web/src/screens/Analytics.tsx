import Quality from '../panels/Quality';

export default function Analytics() {
  return (
    <div>
      <div className="screen-h">
        <h1>Analytics</h1>
      </div>
      <div style={{ padding: 'var(--pad-3) var(--pad-4)' }}>
        <div id="quality">
          <Quality />
        </div>
        {/* capacity slot — Phase 2 */}
        {/* flow slot — Phase 2 */}
      </div>
    </div>
  );
}
