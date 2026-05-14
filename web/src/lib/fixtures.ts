// Deterministic fixture data ported verbatim from design/new-design/data.js.
// Same LCG seed (0xC0FFEE) and constants ensure byte-identical output across
// runs — required by the Phase 0 visual-diff harness.
//
// Operator-specific project names are not baked into this file. The fixture
// payload is loaded at module-init time from /fixtures.local.json (preferred,
// gitignored) or /fixtures.sample.json (committed, generic placeholder data).
// Operators can drop a fixtures.local.json into web/public/ to customise the
// screenshot/Storybook data without touching the repo.
import type {
  Worker,
  BoardEntry,
  FeedItem,
  LoopEvent,
  StatusEntry,
  Project,
  EventsGraph,
  QueueItem,
  PipelineRun,
  PRMonitorEntry,
  Health,
  StatsActivity,
  StatsStage,
  StatsRework,
  Verdict,
  ClaudeUsage,
  ScannerState,
  IssueCostRow,
} from './types';

interface FixtureProject { id: string; repo: string; color?: string }
interface FixtureWorkerInit {
  project: string;
  role: string;
  model: string;
  event_type: string;
  issue_number: number;
  pr_number: number | null;
  detail: string;
  age_seconds: number;
}
interface FixturePayload {
  projects: FixtureProject[];
  workers: FixtureWorkerInit[];
  queueTitles: string[];
}

// Embedded fallback — used when fetch() is unavailable (e.g. node/test envs)
// or when neither fixtures.local.json nor fixtures.sample.json can be loaded.
// Kept in sync with web/public/fixtures.sample.json.
const FALLBACK_PAYLOAD: FixturePayload = {
  projects: [
    { id: 'project-a', repo: 'example-org/project-a', color: 'po' },
    { id: 'project-b', repo: 'example-org/project-b', color: 'dev' },
    { id: 'project-c', repo: 'example-org/project-c', color: 'qa' },
    { id: 'project-d', repo: 'example-org/project-d', color: 'reviewer' },
  ],
  workers: [
    { project: 'project-a', role: 'dev',      model: 'sonnet-4-6', event_type: 'dev_start',    issue_number: 142, pr_number: null, detail: '#142 implement retry backoff', age_seconds: 124 },
    { project: 'project-b', role: 'reviewer', model: 'opus-4-1',   event_type: 'review_start', issue_number: 138, pr_number: 138,  detail: '#138 review PR diff',          age_seconds: 47 },
    { project: 'project-c', role: 'po',       model: 'gpt-5',      event_type: 'po_start',     issue_number: 150, pr_number: null, detail: '#150 spec breakdown',          age_seconds: 12 },
    { project: 'project-d', role: 'qa',       model: 'haiku-4-5',  event_type: 'qa_start',     issue_number: 101, pr_number: null, detail: '#101 run regression suite',    age_seconds: 8 },
    { project: 'project-a', role: 'judge',    model: 'gemini-2-5', event_type: 'judge_start',  issue_number: 88,  pr_number: null, detail: '#88 verdict scoring',          age_seconds: 2 },
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

async function loadPayload(): Promise<FixturePayload> {
  if (typeof fetch !== 'function') return FALLBACK_PAYLOAD;
  for (const url of ['/fixtures.local.json', '/fixtures.sample.json']) {
    try {
      const r = await fetch(url);
      if (r.ok) return (await r.json()) as FixturePayload;
    } catch {
      // ignore and try next
    }
  }
  return FALLBACK_PAYLOAD;
}

const PAYLOAD: FixturePayload = await loadPayload();
const PROJECTS: readonly FixtureProject[] = PAYLOAD.projects;

const ROLES = ['po', 'dev', 'qa', 'reviewer', 'merge', 'judge'] as const;

const AGENTS = [
  { agent: 'claude', model: 'sonnet-4-6' },
  { agent: 'claude', model: 'opus-4-1' },
  { agent: 'claude', model: 'haiku-4-5' },
  { agent: 'gpt',    model: 'gpt-5' },
  { agent: 'gpt',    model: 'gpt-5-mini' },
  { agent: 'gemini', model: 'gemini-2-5' },
] as const;

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

// Deterministic RNG — same LCG constants as design/new-design/data.js
let _seed = 0xC0FFEE;
function resetSeed() { _seed = 0xC0FFEE; }
function rand(): number {
  _seed = (_seed * 1664525 + 1013904223) >>> 0;
  return _seed / 0xFFFFFFFF;
}
function pick<T>(arr: readonly T[]): T { return arr[Math.floor(rand() * arr.length)]; }
function randInt(lo: number, hi: number): number { return lo + Math.floor(rand() * (hi - lo + 1)); }

type RawEvent = LoopEvent & { ts: number; agent: string; points: number; duration_ms: number };

function buildHistory(): RawEvent[] {
  const now = Date.now();
  const events: RawEvent[] = [];
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
      detail: null,
      created_at: new Date(t).toISOString(),
    });
  }
  events.sort((a, b) => b.ts - a.ts);
  return events;
}

// Build once at module load with seed reset so output is always identical
resetSeed();
const HISTORY = buildHistory();

const WORKERS_INITIAL: Worker[] = PAYLOAD.workers.map((w) => ({
  project: w.project,
  role: w.role,
  model: w.model,
  event_type: w.event_type,
  issue_number: w.issue_number,
  pr_number: w.pr_number,
  detail: w.detail,
  created_at: new Date(Date.now() - w.age_seconds * 1000).toISOString(),
}));

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

export function getFixtureVerdicts(): Verdict[] {
  resetSeed();
  return Array.from({ length: 20 }, (_, i) => ({
    id: i + 1,
    project: pick(PROJECTS).id,
    role: pick(ROLES),
    model: pick(AGENTS).model,
    points: randInt(1, 5),
    reason: pick(['auto: dev_done', 'auto: qa_pass', 'manual review'] as const),
    created_at: new Date(Date.now() - randInt(60, 86400) * 1000).toISOString(),
  }));
}

export function getFixtureFeed(): FeedItem[] {
  return HISTORY.slice(0, 50).map((e, i) => ({
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
    age_seconds: Math.floor((Date.now() - e.ts) / 1000),
    status: e.event_type.endsWith('_fail') ? 'fail' : e.event_type.endsWith('_pass') ? 'pass' : 'done',
  }));
}

export function getFixtureHistory(): LoopEvent[] {
  return HISTORY.slice(0, 50).map((e) => ({
    id: e.id,
    project: e.project,
    role: e.role,
    model: e.model,
    event_type: e.event_type,
    issue_number: e.issue_number,
    pr_number: e.pr_number,
    detail: e.detail,
    created_at: e.created_at,
    points: e.points,
  }));
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

const QUEUE_REASONS = ['stuck_label', 'timeout', 'qa_fail_repeated'] as const;

export function getFixtureActionQueue(): QueueItem[] {
  resetSeed();
  const TITLES = PAYLOAD.queueTitles;
  return Array.from({ length: 18 }, (_, i) => {
    const p = pick(PROJECTS);
    return {
      project: p.id,
      kind: 'issue' as const,
      number: randInt(20, 200),
      title: pick(TITLES),
      stage: pick(['blocked', 'needs-clarification', 'in-progress'] as const),
      age_seconds: randInt(60, 6 * 60 * 60),
      reason: pick(QUEUE_REASONS),
      threshold_seconds: null,
      loop_id: null,
      github_url: `https://github.com/${p.repo}/issues/${i + 1}`,
    };
  });
}

export function getFixtureRuns(project: string): PipelineRun[] {
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

export function getFixturePRMonitor(project: string): PRMonitorEntry[] {
  resetSeed();
  const STAGES = ['in-development', 'in-review', 'merged', 'qa-passed'] as const;
  return Array.from({ length: 5 }, (_, i) => ({
    pr_number: randInt(10, 200),
    title: `PR for issue #${randInt(10, 200)}`,
    branch: `feat/issue-${randInt(10, 200)}-fix`,
    stage: pick(STAGES),
    time_in_stage_seconds: randInt(60, 3600),
    retry_count: randInt(0, 2),
    last_event: pick(EVENT_TYPES),
    last_event_at: new Date(Date.now() - randInt(60, 3600) * 1000).toISOString(),
    github_url: `https://github.com/example-org/${project}/pull/${randInt(10, 200)}`,
    is_finished: i > 3,
    is_draft: false,
  }));
}

export function getFixtureHealth(): Health {
  return {
    status: 'ok',
    monitor_version: '0.0.0-fixture',
    git_sha: 'c0ffee0',
    supported_bounty_api: '1.x',
    core_version_counts: { '1.0': 300, '1.1': 45 },
    loop_ids: ['loop-001', 'loop-002'],
  };
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
    { stage: 'dev',    avg_seconds: 1800, count: 120 },
    { stage: 'review', avg_seconds: 900,  count: 95 },
    { stage: 'qa',     avg_seconds: 600,  count: 88 },
    { stage: 'merge',  avg_seconds: 120,  count: 75 },
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

export function getFixtureClaudeUsage(): ClaudeUsage {
  return {
    enabled: true,
    quota_used: 1_250_000,
    quota_limit: 5_000_000,
    quota_pct: 25,
    reset_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
    cache_hit_pct: 42.5,
    refresh_seconds: 300,
    error: null,
  };
}

// Full history for use by transforms (same data that would come from /api/history)
export function getFixtureHistoryAll(): RawEvent[] {
  return HISTORY;
}

export function getFixtureIssuesCost(): IssueCostRow[] {
  resetSeed();
  const PRIORITIES = ['p0-critical', 'p1-high', 'p2-medium', 'p3-low'] as const;
  const STATES = ['open', 'closed', 'in-progress'] as const;
  return Array.from({ length: 20 }, (_) => {
    const p = pick(PROJECTS);
    const actual_runs = randInt(1, 12);
    const rework_factor = parseFloat((actual_runs / 5).toFixed(2));
    const issue_number = randInt(10, 200);
    return {
      project: p.id,
      issue_number,
      priority: pick(PRIORITIES),
      state: pick(STATES),
      rework_factor,
      total_points: randInt(0, 25),
      stranded_seconds: rand() > 0.4 ? randInt(0, 72 * 3600) : null,
      actual_runs,
      last_event_at: new Date(Date.now() - randInt(60, 7 * 86400) * 1000).toISOString(),
      github_url: `https://github.com/${p.repo}/issues/${issue_number}`,
    };
  }).sort((a, b) => b.rework_factor - a.rework_factor || b.actual_runs - a.actual_runs);
}

export function getFixtureScannerState(): ScannerState {
  return {
    stages: {
      po:       { in_flight: 1, cap: 4 },
      dev:      { in_flight: 2, cap: 4 },
      qa:       { in_flight: 0, cap: 4 },
      review: { in_flight: 1, cap: 4 },
      merge:    { in_flight: 0, cap: 2 },
    },
    retries: [
      { project: 'project-b', kind: 'issue', number: 137, stage: 'po',  count: 1, max: 2 },
      { project: 'project-a', kind: 'issue', number: 142, stage: 'dev', count: 2, max: 2 },
    ],
  };
}
