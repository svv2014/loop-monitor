// Deterministic fixture data ported verbatim from design/new-design/data.js.
// The seeded RNG must produce byte-identical output to the prototype so
// ?fixtures=1 renders deterministically across runs (Phase 0 visual-diff depends on this).
import type {
  Worker,
  BoardEntry,
  FeedItem,
  LoopEvent,
  StatusEntry,
  Project,
  EventsGraph,
  QueueItem,
  Health,
  StatsActivity,
  StatsStage,
  StatsRework,
} from './types';

const PROJECTS = [
  { id: 'loop',               repo: 'svv2014/loop' },
  { id: 'loop-monitor',       repo: 'svv2014/loop-monitor' },
  { id: 'boba-event',         repo: 'svv2014/boba-event' },
  { id: 'boba-orchestrator',  repo: 'svv2014/boba-orchestrator' },
  { id: 'ntc',                repo: 'svv2014/NanoTraderCopilot' },
  { id: 'pa-scanner',         repo: 'svv2014/pa-scanner' },
  { id: 'ppl',                repo: 'svv2014/ppl-study' },
  { id: 'suprun',             repo: 'svv2014/suprun' },
  { id: 'vrefm-classifier',   repo: 'svv2014/vrefm-classifier' },
];

const ROLES = ['po', 'dev', 'qa', 'reviewer', 'merge', 'judge'] as const;

const AGENTS = [
  { agent: 'claude', model: 'sonnet-4-6' },
  { agent: 'claude', model: 'opus-4-1' },
  { agent: 'claude', model: 'haiku-4-5' },
  { agent: 'gpt',    model: 'gpt-5' },
  { agent: 'gpt',    model: 'gpt-5-mini' },
  { agent: 'gemini', model: 'gemini-2-5' },
];

const EVENT_TYPES = [
  'po_start', 'po_done',
  'dev_start', 'dev_done',
  'qa_pass', 'qa_fail',
  'review_done',
  'merge_done',
  'judge_done',
] as const;

const ROLE_BY_EVENT: Record<string, string> = {
  po_start: 'po', po_done: 'po',
  dev_start: 'dev', dev_done: 'dev',
  qa_pass: 'qa', qa_fail: 'qa',
  review_done: 'reviewer',
  merge_done: 'merge',
  judge_done: 'judge',
};

// Deterministic RNG — same LCG constants as data.js
let _seed = 0xC0FFEE;
function rand(): number {
  _seed = (_seed * 1664525 + 1013904223) >>> 0;
  return _seed / 0xFFFFFFFF;
}
function pick<T>(arr: readonly T[]): T { return arr[Math.floor(rand() * arr.length)]; }
function randInt(lo: number, hi: number): number { return lo + Math.floor(rand() * (hi - lo + 1)); }

function buildHistory(): LoopEvent[] {
  const now = Date.now();
  const events: LoopEvent[] = [];
  const DAY = 24 * 60 * 60 * 1000;
  for (let i = 0; i < 600; i++) {
    const t = now - rand() * DAY;
    const event_type = pick(EVENT_TYPES);
    const role = ROLE_BY_EVENT[event_type];
    const project = pick(PROJECTS);
    const ag = pick(AGENTS);
    const pts = ['merge_done', 'judge_done', 'dev_done', 'po_done', 'review_done'].includes(event_type)
      ? randInt(1, 5) : 0;
    events.push({
      id: i,
      ts: t,
      event_type,
      role,
      agent: ag.agent,
      model: ag.model,
      project: project.id,
      issue_number: randInt(20, 150),
      pr_number: randInt(20, 150),
      points: pts,
      duration_ms: randInt(800, 240000),
      created_at: new Date(t).toISOString(),
    } as LoopEvent & { ts: number; agent: string; duration_ms: number; points: number });
  }
  events.sort((a, b) => (b as unknown as { ts: number }).ts - (a as unknown as { ts: number }).ts);
  return events;
}

// Reset seed before building so fixture data is deterministic on every call
function resetSeed() { _seed = 0xC0FFEE; }

resetSeed();
const HISTORY = buildHistory();

const WORKERS_INITIAL: Worker[] = [
  { project: 'loop',            role: 'dev',      model: 'sonnet-4-6', event_type: 'dev_start',    issue_number: 142, pr_number: null,  detail: '#142 implement retry backoff', created_at: new Date(Date.now() - 124_000).toISOString() },
  { project: 'loop-monitor',    role: 'reviewer', model: 'opus-4-1',   event_type: 'review_start',  issue_number: 138, pr_number: 138,   detail: '#138 review PR diff',          created_at: new Date(Date.now() - 47_000).toISOString() },
  { project: 'ppl',             role: 'po',       model: 'gpt-5',      event_type: 'po_start',      issue_number: 150, pr_number: null,  detail: '#150 spec breakdown',          created_at: new Date(Date.now() - 12_000).toISOString() },
  { project: 'vrefm-classifier',role: 'qa',       model: 'haiku-4-5',  event_type: 'qa_start',      issue_number: 101, pr_number: null,  detail: '#101 run regression suite',    created_at: new Date(Date.now() - 8_000).toISOString() },
  { project: 'boba-event',      role: 'judge',    model: 'gemini-2-5', event_type: 'judge_start',   issue_number: 88,  pr_number: null,  detail: '#88 verdict scoring',          created_at: new Date(Date.now() - 2_300).toISOString() },
];

function buildQueue(): QueueItem[] {
  resetSeed();
  const PRIORITIES = ['critical', 'high', 'normal', 'low'] as const;
  const TITLES = [
    'rate-limit handler exceeds budget',
    'flaky test in pipeline_runs',
    'spec drift on /api/report v1.2',
    'judge gives low verdict on small diffs',
    'memory leak in event ingest loop',
    'queue starvation under burst load',
    'webhook timeout retries unbounded',
    'leaderboard ranks tied agents wrong',
    'duplicate events from boba-orchestrator',
    'missing duration on judge_done',
  ];
  const items: QueueItem[] = [];
  for (let i = 0; i < 18; i++) {
    const p = pick(PROJECTS);
    const role = pick(ROLES);
    items.push({
      project: p.id,
      kind: 'issue',
      number: randInt(20, 200),
      title: pick(TITLES),
      stage: pick(['blocked', 'needs-clarification', 'in-progress']),
      age_seconds: randInt(60, 6 * 60 * 60),
      reason: pick(['stuck_label', 'timeout', 'qa_fail_repeated']),
      loop_id: null,
      github_url: `https://github.com/${p.repo}/issues/${randInt(20, 200)}`,
      role,
    } as QueueItem & { role: string });
  }
  items.sort((a, b) => PRIORITIES.indexOf(a.reason as never) - PRIORITIES.indexOf(b.reason as never));
  return items;
}

// Build all fixture data lazily (reset seed each time for consistency)
export function getFixtureActive(): Worker[] {
  return WORKERS_INITIAL;
}

export function getFixtureBoard(): BoardEntry[] {
  resetSeed();
  return ROLES.map((role) => ({
    project: pick(PROJECTS).id,
    role,
    model: pick(AGENTS).model,
    total_points: randInt(10, 200),
    verdict_count: randInt(2, 40),
  }));
}

export function getFixtureFeed(): FeedItem[] {
  return HISTORY.slice(0, 50).map((e, i) => {
    const ev = e as unknown as { ts: number; agent: string; points: number };
    return {
      id: i,
      project: e.project,
      role: e.role,
      model: e.model,
      event_type: e.event_type,
      issue_number: e.issue_number,
      pr_number: e.pr_number,
      detail: null,
      payload: null,
      created_at: e.created_at,
      age_seconds: Math.floor((Date.now() - ev.ts) / 1000),
      status: e.event_type.endsWith('_fail') ? 'fail' : e.event_type.endsWith('_pass') ? 'pass' : 'done',
    };
  });
}

export function getFixtureHistory(): LoopEvent[] {
  return HISTORY.slice(0, 50);
}

export function getFixtureStatus(): StatusEntry[] {
  return WORKERS_INITIAL.map((w) => ({
    project: w.project,
    role: w.role,
    model: w.model,
    event_type: w.event_type,
    issue_number: w.issue_number,
    pr_number: w.pr_number,
    detail: w.detail,
    payload: null,
    created_at: w.created_at,
  }));
}

export function getFixtureProjects(): Project[] {
  return PROJECTS.map((p) => ({ project: p.id, repo: p.repo }));
}

export function getFixtureEventsGraph(): EventsGraph {
  resetSeed();
  const buckets = Array.from({ length: 24 }, (_, i) => {
    const hour = new Date(Date.now() - (23 - i) * 3_600_000);
    return ROLES.map((role) => ({
      hour: hour.toISOString().slice(0, 13) + ':00:00',
      role,
      count: randInt(0, 20),
    }));
  }).flat();
  return { window_hours: 24, buckets };
}

export function getFixtureActionQueue(): QueueItem[] {
  return buildQueue();
}

export function getFixtureRuns(project: string): import('./types').PipelineRun[] {
  resetSeed();
  return Array.from({ length: 10 }, (_, i) => ({
    id: i + 1,
    project,
    issue_number: randInt(10, 200),
    pr_number: randInt(10, 200),
    title: `Issue #${randInt(10, 200)} auto-fix attempt`,
    outcome: pick(['clean', 'failed', null] as const),
    started_at: new Date(Date.now() - randInt(1000, 86400) * 1000).toISOString(),
    completed_at: new Date(Date.now() - randInt(0, 1000) * 1000).toISOString(),
    total_duration_seconds: randInt(60, 3600),
    rework_count: randInt(0, 3),
    total_bounty: randInt(0, 20),
    created_at: new Date(Date.now() - randInt(1000, 86400) * 1000).toISOString(),
  }));
}

export function getFixturePRMonitor(project: string): import('./types').PRMonitorEntry[] {
  resetSeed();
  const STAGES = ['in-development', 'in-review', 'merged', 'qa-passed'];
  return Array.from({ length: 5 }, (_, i) => ({
    pr_number: randInt(10, 200),
    title: `PR for issue #${randInt(10, 200)}`,
    branch: `feat/issue-${randInt(10, 200)}-fix`,
    stage: pick(STAGES),
    time_in_stage_seconds: randInt(60, 3600),
    retry_count: randInt(0, 2),
    last_event: pick(EVENT_TYPES as unknown as string[]),
    last_event_at: new Date(Date.now() - randInt(60, 3600) * 1000).toISOString(),
    github_url: `https://github.com/svv2014/${project}/pull/${randInt(10, 200)}`,
    is_finished: i > 3,
    is_draft: false,
  }));
}

export function getFixtureHealth(): Health {
  return {
    status: 'ok',
    monitor_version: '0.0.0-fixture',
    git_sha: 'c0ffee',
    supported_bounty_api: '1.x',
    core_version_counts: { '1.0': 300, '1.1': 45 },
    loop_ids: ['loop-001', 'loop-002'],
  };
}

export function getFixtureVerdicts(): import('./types').Verdict[] {
  resetSeed();
  return Array.from({ length: 20 }, (_, i) => ({
    id: i + 1,
    project: pick(PROJECTS).id,
    role: pick(ROLES),
    model: pick(AGENTS).model,
    points: randInt(1, 5),
    reason: pick(['auto: dev_done', 'auto: qa_pass', 'manual review']),
    created_at: new Date(Date.now() - randInt(60, 86400) * 1000).toISOString(),
  }));
}

export function getFixtureStatsActivity(): StatsActivity[] {
  resetSeed();
  return PROJECTS.slice(0, 5).flatMap((p) =>
    Array.from({ length: 7 }, (_, i) => ({
      date: new Date(Date.now() - i * 86400_000).toISOString().slice(0, 10),
      project: p.id,
      n: randInt(0, 30),
    }))
  );
}

export function getFixtureStatsStages(): StatsStage[] {
  return [
    { stage: 'dev', avg_seconds: 1800, count: 120 },
    { stage: 'review', avg_seconds: 900, count: 95 },
    { stage: 'qa', avg_seconds: 600, count: 88 },
    { stage: 'merge', avg_seconds: 120, count: 75 },
  ];
}

export function getFixtureStatsRework(): StatsRework[] {
  resetSeed();
  return PROJECTS.map((p) => ({
    project: p.id,
    rework_starts: randInt(0, 20),
    review_dones: randInt(5, 40),
  }));
}

// Raw history for use by transforms (same data that would come from /api/history)
export function getFixtureHistoryAll(): LoopEvent[] {
  return HISTORY;
}
