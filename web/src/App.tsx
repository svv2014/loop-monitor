import { useState } from 'react';
import Logo from './components/Logo';
import NavRail from './components/NavRail';
import TopBar from './components/TopBar';
import './lib/tokens.css';
import Queue from './screens/Queue';

export default function App() {
  const [screen, setScreen] = useState('overview');

  return (
    <div className="app">
      <Logo />
      <TopBar events={[]} online={false} version="0.0.0" />
      <NavRail screen={screen} setScreen={setScreen} />
      <main className="main">
        {screen === 'queue' && <Queue />}
      </main>
    </div>
  );
}
