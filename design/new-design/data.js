// Pipeline Monitor — mock data layer
// Modeled after the Loop Monitor event schema:
//   events: dev_start, dev_done, po_start, po_done, qa_pass, qa_fail,
//           review_done, merge_done, judge_done
//   roles: po, dev, qa, reviewer, merge, judge

(function () {
  const PROJECTS = [
    { id: 'loop',           color: 'po' },
    { id: 'loop-monitor',   color: 'dev' },
    { id: 'boba-event',     color: 'qa' },
    { id: 'boba-orchestrator', color: 'reviewer' },
    { id: 'ntc',            color: 'merge' },
    { id: 'pa-scanner',     color: 'judge' },
    { id: 'ppl',            color: 'dev' },
    { id: 'suprun',         color: 'po' },
    { id: 'vrefm-classifier', color: 'qa' },
  ];

  const ROLES = ['po', 'dev', 'qa', 'reviewer', 'merge', 'judge'];

  const AGENTS = [
    { agent: 'claude',  model: 'sonnet-4-6'  },
    { agent: 'claude',  model: 'opus-4-1'    },
    { agent: 'claude',  model: 'haiku-4-5'   },
    { agent: 'gpt',     model: 'gpt-5'       },
    { agent: 'gpt',     model: 'gpt-5-mini'  },
    { agent: 'gemini',  model: 'gemini-2-5'  },
  ];

  const EVENT_TYPES = [
    'po_start', 'po_done',
    'dev_start', 'dev_done',
    'qa_pass', 'qa_fail',
    'review_done',
    'merge_done',
    'judge_done',
  ];

  const ROLE_BY_EVENT = {
    po_start: 'po', po_done: 'po',
    dev_start: 'dev', dev_done: 'dev',
    qa_pass: 'qa', qa_fail: 'qa',
    review_done: 'reviewer',
    merge_done: 'merge',
    judge_done: 'judge',
  };

  // Deterministic-ish RNG so reloads don't shuffle history
  let _seed = 0xC0FFEE;
  function rand() {
    _seed = (_seed * 1664525 + 1013904223) >>> 0;
    return _seed / 0xFFFFFFFF;
  }
  function pick(arr) { return arr[Math.floor(rand() * arr.length)]; }
  function pickN(arr, n) { return Array.from({length: n}, () => pick(arr)); }
  function randInt(lo, hi) { return lo + Math.floor(rand() * (hi - lo + 1)); }

  // Build seed history of events (last 24h, ~600 events)
  function buildHistory() {
    const now = Date.now();
    const events = [];
    const DAY = 24 * 60 * 60 * 1000;
    for (let i = 0; i < 600; i++) {
      const t = now - rand() * DAY;
      const event = pick(EVENT_TYPES);
      const role = ROLE_BY_EVENT[event];
      const project = pick(PROJECTS);
      const ag = pick(AGENTS);
      events.push({
        id: `e${i}`,
        ts: t,
        event,
        role,
        agent: ag.agent,
        model: ag.model,
        project: project.id,
        issue_num: randInt(20, 150),
        pr_num: randInt(20, 150),
        points: ['merge_done', 'judge_done', 'dev_done', 'po_done', 'review_done'].includes(event)
          ? randInt(1, 5) : 0,
        duration_ms: randInt(800, 240000),
      });
    }
    events.sort((a, b) => b.ts - a.ts);
    return events;
  }

  // Workers — agents currently busy (simulated)
  const WORKERS_INITIAL = [
    { id: 'w1', name: 'sonnet-4-6',  agent: 'claude',  model: 'sonnet-4-6',  role: 'dev',      project: 'loop',           task: '#142 implement retry backoff', startedAt: Date.now() - 124_000, status: 'busy' },
    { id: 'w2', name: 'opus-4-1',    agent: 'claude',  model: 'opus-4-1',    role: 'reviewer', project: 'loop-monitor',   task: '#138 review PR diff',          startedAt: Date.now() - 47_000,  status: 'busy' },
    { id: 'w3', name: 'gpt-5',       agent: 'gpt',     model: 'gpt-5',       role: 'po',       project: 'ppl',            task: '#150 spec breakdown',          startedAt: Date.now() - 12_000,  status: 'busy' },
    { id: 'w4', name: 'haiku-4-5',   agent: 'claude',  model: 'haiku-4-5',   role: 'qa',       project: 'vrefm-classifier', task: '#101 run regression suite',  startedAt: Date.now() - 8_000,   status: 'busy' },
    { id: 'w5', name: 'gemini-2-5',  agent: 'gemini',  model: 'gemini-2-5',  role: 'judge',    project: 'boba-event',     task: '#88 verdict scoring',          startedAt: Date.now() - 2_300,   status: 'busy' },
  ];

  // Aggregate helpers
  function buildLeaderboard(events, by = 'role') {
    const map = new Map();
    for (const e of events) {
      const key = by === 'role' ? e.role : `${e.agent}/${e.model}`;
      if (!map.has(key)) map.set(key, { key, verdicts: 0, points: 0 });
      const row = map.get(key);
      row.points += e.points;
      if (e.points > 0) row.verdicts += 1;
    }
    return Array.from(map.values()).sort((a, b) => b.points - a.points);
  }

  function buildProjectStatus(events, workers) {
    const byProject = new Map();
    for (const p of PROJECTS) {
      byProject.set(p.id, {
        id: p.id, color: p.color, lastEvent: null, lastTs: 0,
        status: 'idle', points: 0, totalEvents: 0, busyWorker: null,
      });
    }
    for (const e of events) {
      const row = byProject.get(e.project);
      if (!row) continue;
      row.totalEvents += 1;
      row.points += e.points;
      if (e.ts > row.lastTs) {
        row.lastTs = e.ts;
        row.lastEvent = e.event;
      }
    }
    for (const w of workers) {
      const row = byProject.get(w.project);
      if (row) { row.status = 'busy'; row.busyWorker = w; }
    }
    return Array.from(byProject.values()).sort((a, b) => b.points - a.points);
  }

  function build24hBuckets(events) {
    const buckets = Array.from({length: 24}, (_, i) => ({
      hour: i,
      counts: { po: 0, dev: 0, qa: 0, reviewer: 0, merge: 0, judge: 0 },
      total: 0,
    }));
    const now = Date.now();
    for (const e of events) {
      const hoursAgo = Math.floor((now - e.ts) / (60 * 60 * 1000));
      if (hoursAgo < 0 || hoursAgo >= 24) continue;
      const idx = 23 - hoursAgo;
      buckets[idx].counts[e.role] = (buckets[idx].counts[e.role] || 0) + 1;
      buckets[idx].total += 1;
    }
    return buckets;
  }

  // Action queue — pending pipeline tasks waiting for a worker
  function buildQueue() {
    const items = [];
    const PRIORITIES = ['critical', 'high', 'normal', 'low'];
    for (let i = 0; i < 18; i++) {
      const p = pick(PROJECTS);
      const role = pick(ROLES);
      items.push({
        id: `q${i}`,
        project: p.id,
        role,
        issue_num: randInt(20, 200),
        title: pick([
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
        ]),
        priority: pick(PRIORITIES),
        waiting_ms: randInt(60_000, 6 * 60 * 60 * 1000),
        attempts: randInt(0, 2),
      });
    }
    return items.sort((a, b) => PRIORITIES.indexOf(a.priority) - PRIORITIES.indexOf(b.priority));
  }

  const HISTORY = buildHistory();
  const QUEUE = buildQueue();

  window.PipelineData = {
    PROJECTS, ROLES, AGENTS, EVENT_TYPES, ROLE_BY_EVENT,
    HISTORY, QUEUE,
    WORKERS_INITIAL,
    buildLeaderboard, buildProjectStatus, build24hBuckets,
    rand, pick, randInt,
  };
})();
