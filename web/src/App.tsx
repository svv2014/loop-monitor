import Logo from './components/Logo';
import TopBar from './components/TopBar';
import NavRail from './components/NavRail';
import { useState } from 'react';

export default function App() {
  const [screen, setScreen] = useState('overview');

  return (
    <div className="app">
      <Logo />
      <TopBar events={[]} online={false} version="0.0.0" />
      <NavRail screen={screen} setScreen={setScreen} />
      <main className="main"></main>
    </div>
  );
}
