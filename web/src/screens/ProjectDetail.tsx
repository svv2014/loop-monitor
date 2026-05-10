import ScannerState from '../panels/ScannerState';

interface Props {
  projectId: string;
}

export default function ProjectDetail({ projectId }: Props) {
  return (
    <div style={{ padding: 'var(--pad-4)', display: 'grid', gap: 'var(--pad-3)' }}>
      <div className="screen-h">
        <h1>{projectId}</h1>
      </div>
      <ScannerState projectId={projectId} />
    </div>
  );
}
