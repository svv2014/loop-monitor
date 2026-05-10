import Charts from '../panels/Charts';
import ClaudeUsage from '../panels/ClaudeUsage';

export default function Overview() {
  return (
    <div>
      <div className="screen-h">
        <h1>Overview</h1>
      </div>
      <ClaudeUsage />
      <Charts />
    </div>
  );
}
