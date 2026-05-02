/* global React, ReactDOM, PipelineData, PMComponents, PMScreens, TweaksPanel, useTweaks, TweakSection, TweakSlider, TweakRadio, TweakToggle, TweakSelect */
const { useState, useEffect, useMemo, useRef } = React;
const { Logo, TopBar, NavRail } = PMComponents;
const { OverviewScreen, QueueScreen, ProjectDetail, WorkerDetail } = PMScreens;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "density": "cozy",
  "accent": "green",
  "showGrain": true,
  "liveSpeed": "normal"
}/*EDITMODE-END*/;

const ACCENTS = {
  green:  { c: 'oklch(0.82 0.18 145)', c2: 'oklch(0.62 0.18 145)' },
  amber:  { c: 'oklch(0.82 0.16 80)',  c2: 'oklch(0.62 0.16 80)'  },
  cyan:   { c: 'oklch(0.80 0.14 210)', c2: 'oklch(0.60 0.14 210)' },
  violet: { c: 'oklch(0.78 0.16 295)', c2: 'oklch(0.58 0.16 295)' },
};
const DENSITY_MAP = { compact: 0.85, cozy: 1, roomy: 1.15 };
const SPEED_MAP   = { slow: 5000, normal: 2000, fast: 800 };

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [screen, setScreen] = useState('overview');
  const [events, setEvents] = useState(() => PipelineData.HISTORY.map(e => ({ ...e })));
  const [workers, setWorkers] = useState(() => PipelineData.WORKERS_INITIAL.map(w => ({ ...w })));
  const [selectedProject, setSelectedProject] = useState('loop');
  const [selectedWorker, setSelectedWorker] = useState(null);

  // Apply tweaks to root css
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--d', String(DENSITY_MAP[tweaks.density] || 1));
    const a = ACCENTS[tweaks.accent] || ACCENTS.green;
    root.style.setProperty('--accent', a.c);
    root.style.setProperty('--accent-2', a.c2);
    if (tweaks.showGrain) document.body.classList.remove('no-grain');
    else document.body.classList.add('no-grain');
  }, [tweaks]);

  // Live event simulator — periodically push new events + cycle workers
  useEffect(() => {
    const interval = SPEED_MAP[tweaks.liveSpeed] || 2000;
    const id = setInterval(() => {
      // 1) Generate new event from a random worker (or random)
      const ROLE_BY_EVENT = PipelineData.ROLE_BY_EVENT;
      const EVENT_TYPES = PipelineData.EVENT_TYPES;
      const useWorker = workers.length > 0 && Math.random() < 0.7;
      const w = useWorker ? workers[Math.floor(Math.random() * workers.length)] : null;
      const event = w
        ? PipelineData.pick([`${w.role}_done`, `${w.role}_start`, 'qa_pass', 'review_done'].filter(e => EVENT_TYPES.includes(e)))
        : PipelineData.pick(EVENT_TYPES);
      const role = ROLE_BY_EVENT[event] || (w?.role) || 'dev';
      const project = w?.project || PipelineData.pick(PipelineData.PROJECTS).id;
      const ag = w ? { agent: w.agent, model: w.model } : PipelineData.pick(PipelineData.AGENTS);
      const points = ['merge_done', 'judge_done', 'dev_done', 'po_done', 'review_done'].includes(event)
        ? PipelineData.randInt(1, 5) : 0;
      const newEvent = {
        id: `live-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        ts: Date.now(),
        event, role,
        agent: ag.agent, model: ag.model,
        project,
        issue_num: w ? PipelineData.randInt(20, 200) : PipelineData.randInt(20, 200),
        pr_num: PipelineData.randInt(20, 200),
        points,
        duration_ms: PipelineData.randInt(1000, 60000),
        _fresh: true,
      };

      setEvents(prev => [newEvent, ...prev].slice(0, 800));

      // 2) Cycle workers occasionally — finish one, spawn new
      if (Math.random() < 0.3) {
        setWorkers(prev => {
          const TASKS = [
            'rate-limit handler tweak', 'investigate flaky test',
            'spec walk-through', 'review PR diff', 'verdict scoring',
            'regression suite', 'merge conflict resolve', 'retry backoff fix',
            'doc update', 'event ingest tuning',
          ];
          // Maybe drop one
          let next = [...prev];
          if (next.length > 2 && Math.random() < 0.4) {
            const drop = Math.floor(Math.random() * next.length);
            next.splice(drop, 1);
          }
          // Maybe add one
          if (next.length < 6 && Math.random() < 0.6) {
            const ag = PipelineData.pick(PipelineData.AGENTS);
            const role = PipelineData.pick(['po', 'dev', 'qa', 'reviewer', 'merge', 'judge']);
            const proj = PipelineData.pick(PipelineData.PROJECTS).id;
            next.push({
              id: `w-live-${Date.now()}`,
              name: ag.model,
              agent: ag.agent,
              model: ag.model,
              role,
              project: proj,
              task: `#${PipelineData.randInt(20, 200)} ${PipelineData.pick(TASKS)}`,
              startedAt: Date.now() - PipelineData.randInt(0, 30000),
              status: 'busy',
            });
          }
          return next;
        });
      }
    }, interval);
    return () => clearInterval(id);
  }, [workers, tweaks.liveSpeed]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.key === '1') setScreen('overview');
      if (e.key === '2') setScreen('queue');
      if (e.key === '3') setScreen('projects');
      if (e.key === '4') setScreen('workers');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const navScreen = ['overview', 'queue', 'projects', 'workers'].includes(screen) ? screen : 'overview';

  return (
    <div className="app">
      <Logo/>
      <TopBar events={events} online={true} version="0.2.0"/>
      <NavRail screen={navScreen} setScreen={setScreen}/>
      <div className="main">
        {screen === 'overview' && (
          <OverviewScreen
            events={events}
            workers={workers}
            setScreen={setScreen}
            setSelectedProject={setSelectedProject}
            setSelectedWorker={setSelectedWorker}
          />
        )}
        {screen === 'queue' && <QueueScreen events={events}/>}
        {screen === 'projects' && (
          <ProjectDetail
            projectId={selectedProject}
            events={events}
            workers={workers}
            setScreen={setScreen}
            setSelectedProject={setSelectedProject}
          />
        )}
        {screen === 'project' && (
          <ProjectDetail
            projectId={selectedProject}
            events={events}
            workers={workers}
            setScreen={setScreen}
            setSelectedProject={setSelectedProject}
          />
        )}
        {screen === 'workers' && (
          <WorkerDetail
            workerId={selectedWorker}
            events={events}
            workers={workers}
            setScreen={setScreen}
          />
        )}
      </div>

      <TweaksPanel title="Tweaks">
        <TweakSection title="Layout">
          <TweakRadio label="Density" value={tweaks.density}
            onChange={v => setTweak('density', v)}
            options={[
              { value: 'compact', label: 'Compact' },
              { value: 'cozy',    label: 'Cozy' },
              { value: 'roomy',   label: 'Roomy' },
            ]}/>
        </TweakSection>
        <TweakSection title="Accent">
          <TweakRadio label="Color" value={tweaks.accent}
            onChange={v => setTweak('accent', v)}
            options={[
              { value: 'green',  label: 'Green' },
              { value: 'amber',  label: 'Amber' },
              { value: 'cyan',   label: 'Cyan' },
              { value: 'violet', label: 'Violet' },
            ]}/>
        </TweakSection>
        <TweakSection title="Live feed">
          <TweakRadio label="Event speed" value={tweaks.liveSpeed}
            onChange={v => setTweak('liveSpeed', v)}
            options={[
              { value: 'slow',   label: 'Slow' },
              { value: 'normal', label: 'Normal' },
              { value: 'fast',   label: 'Fast' },
            ]}/>
        </TweakSection>
        <TweakSection title="Visual">
          <TweakToggle label="Background grain"
            value={tweaks.showGrain}
            onChange={v => setTweak('showGrain', v)}/>
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
