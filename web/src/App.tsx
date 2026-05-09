import { useState } from 'react';
import { TopBar } from './components/TopBar';

export function App() {
  const [loopId, setLoopId] = useState('');

  return (
    <div>
      <TopBar loopId={loopId} onLoopChange={setLoopId} />
      <main style={{ padding: '1rem' }}>
        <p>Loop Monitor v2 — Phase 3 screens coming soon.</p>
      </main>
    </div>
  );
}
