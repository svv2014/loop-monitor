import { useState } from 'react';
import Logo from './components/Logo';
import TopBar from './components/TopBar';
import NavRail from './components/NavRail';
import Overview from './screens/Overview';

export default function App() {
  const [screen, setScreen] = useState('overview');
  const [, setSelectedProject] = useState<string | null>(null);

  return (
    <div className="app">
      <Logo />
      <TopBar events={[]} online={false} version="0.0.0" />
      <NavRail screen={screen} setScreen={setScreen} />
      <main className="main">
        {screen === 'overview' && (
          <Overview
            setSelectedProject={setSelectedProject}
            setScreen={setScreen}
          />
        )}
      </main>
    </div>
  );
}
