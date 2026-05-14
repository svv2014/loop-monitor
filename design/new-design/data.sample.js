// Generic placeholder payload for the design prototype.
// See data.js for how this is loaded. Operators can create data.local.js
// (gitignored) exporting the same `window.PipelineDataPayload` shape to
// render the prototype with private project names.
window.PipelineDataPayload = {
  projects: [
    { id: 'project-a', color: 'po' },
    { id: 'project-b', color: 'dev' },
    { id: 'project-c', color: 'qa' },
    { id: 'project-d', color: 'reviewer' },
  ],
  workers: [
    { id: 'w1', name: 'sonnet-4-6', agent: 'claude', model: 'sonnet-4-6', role: 'dev',      project: 'project-a', task: '#142 implement retry backoff', ageMs: 124_000 },
    { id: 'w2', name: 'opus-4-1',   agent: 'claude', model: 'opus-4-1',   role: 'reviewer', project: 'project-b', task: '#138 review PR diff',          ageMs: 47_000 },
    { id: 'w3', name: 'gpt-5',      agent: 'gpt',    model: 'gpt-5',      role: 'po',       project: 'project-c', task: '#150 spec breakdown',          ageMs: 12_000 },
    { id: 'w4', name: 'haiku-4-5',  agent: 'claude', model: 'haiku-4-5',  role: 'qa',       project: 'project-d', task: '#101 run regression suite',    ageMs: 8_000 },
    { id: 'w5', name: 'gemini-2-5', agent: 'gemini', model: 'gemini-2-5', role: 'judge',    project: 'project-a', task: '#88 verdict scoring',          ageMs: 2_300 },
  ],
  queueTitles: [
    'rate-limit handler exceeds budget',
    'flaky test in pipeline_runs',
    'spec drift on /api/report v1.2',
    'judge gives low verdict on small diffs',
    'memory leak in event ingest loop',
    'queue starvation under burst load',
    'webhook timeout retries unbounded',
    'leaderboard ranks tied agents wrong',
    'duplicate events from project-b',
    'missing duration on judge_done',
  ],
};
