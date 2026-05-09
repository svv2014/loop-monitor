import { useEffect, useState } from 'react';
import { ProjectDetail } from './screens/ProjectDetail';
import { useHashRoute } from './router';
import { useProjectStatus } from './hooks/useProjectDetail';
import './styles/globals.css';

export function App() {
  const { screen, projectId, navigateTo } = useHashRoute();
  const statusQuery = useProjectStatus();

  const allProjectIds: string[] = Array.from(
    new Set((statusQuery.data ?? []).map((e) => e.project)),
  ).sort();

  const [resolvedProject, setResolvedProject] = useState<string | null>(projectId);

  // When hash changes to a project, resolve it
  useEffect(() => {
    if (screen === 'project' && projectId) {
      setResolvedProject(projectId);
    }
  }, [screen, projectId]);

  function handleSetProjectId(id: string) {
    setResolvedProject(id);
    navigateTo('project', id);
  }

  function handleSetScreen(s: 'overview' | 'project') {
    if (s === 'overview') {
      navigateTo('overview');
    }
  }

  if (screen === 'project' && resolvedProject) {
    return (
      <ProjectDetail
        projectId={resolvedProject}
        setScreen={handleSetScreen}
        setProjectId={handleSetProjectId}
        allProjectIds={allProjectIds.length > 0 ? allProjectIds : [resolvedProject]}
      />
    );
  }

  // Fallback overview placeholder — full overview is Phase 3.1 (#116)
  return (
    <div style={{ padding: 'var(--pad-4)', fontFamily: 'var(--font-mono)', color: 'var(--fg-3)' }}>
      <p>Loop Monitor v2 — select a project via <code style={{ color: 'var(--accent)' }}>#project=&lt;id&gt;</code></p>
      {allProjectIds.length > 0 && (
        <ul style={{ listStyle: 'none', padding: 0, display: 'grid', gap: 'var(--pad-2)' }}>
          {allProjectIds.map((id) => (
            <li key={id}>
              <button className="btn" onClick={() => handleSetProjectId(id)}>{id}</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
