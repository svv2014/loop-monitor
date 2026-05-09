import { useState, useEffect } from 'react';
import Logo from './components/Logo';
import { TopBar } from './components/TopBar';
import NavRail from './components/NavRail';
import WorkerDetail from './screens/WorkerDetail';

type Screen = 'overview' | 'queue' | 'projects' | 'workers';

const KEYMAP: Record<string, Screen> = {
  '1': 'overview',
  '2': 'queue',
  '3': 'projects',
  '4': 'workers',
};

export function App() {
  const [screen, setScreen] = useState<Screen>('overview');

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const next = KEYMAP[e.key];
      if (next) setScreen(next);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <div className="app">
      <Logo />
      <TopBar />
      <NavRail screen={screen} setScreen={s => setScreen(s as Screen)} />
      <main className="main">
        {screen === 'workers' ? (
          <WorkerDetail setScreen={s => setScreen(s as Screen)} />
        ) : (
          <div style={{
            padding: 'var(--pad-4)',
            color: 'var(--fg-3)',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
          }}>
            {screen} — coming soon (Phase 3.{screen === 'overview' ? '1' : screen === 'queue' ? '2' : '3'})
          </div>
        )}
      </main>
    </div>
  );
}
