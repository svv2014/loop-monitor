export default function Analytics() {
  return (
    <div>
      <div className="screen-h">
        <h1>Analytics</h1>
      </div>
      <div style={{
        padding: 'var(--pad-4)',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--pad-3)',
      }}>
        <section className="panel" style={{ gridColumn: '1 / -1' }}>
          <div className="panel-h"><span>Velocity</span></div>
          <div style={{ padding: 'var(--pad-3) var(--pad-4)', color: 'var(--fg-4)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
            Coming soon
          </div>
        </section>

        <section className="panel">
          <div className="panel-h"><span>Cycle time</span></div>
          <div style={{ padding: 'var(--pad-3) var(--pad-4)', color: 'var(--fg-4)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
            Coming soon
          </div>
        </section>

        <section className="panel">
          <div className="panel-h"><span>Quality</span></div>
          <div style={{ padding: 'var(--pad-3) var(--pad-4)', color: 'var(--fg-4)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
            Coming soon
          </div>
        </section>

        <section className="panel">
          <div className="panel-h"><span>Capacity</span></div>
          <div style={{ padding: 'var(--pad-3) var(--pad-4)', color: 'var(--fg-4)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
            Coming soon
          </div>
        </section>

        <section className="panel">
          <div className="panel-h"><span>Flow</span></div>
          <div style={{ padding: 'var(--pad-3) var(--pad-4)', color: 'var(--fg-4)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
            Coming soon
          </div>
        </section>
      </div>
    </div>
  );
}
