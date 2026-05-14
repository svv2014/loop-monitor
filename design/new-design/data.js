// Pipeline Monitor — mock data layer
// Modeled after the Loop Monitor event schema:
//   events: dev_start, dev_done, po_start, po_done, qa_pass, qa_fail,
//           review_done, merge_done, judge_done
//   roles: po, dev, qa, reviewer, merge, judge
//
// Project names and worker assignments are loaded from a sibling payload
// script (data.sample.js — committed, generic; or data.local.js — gitignored)
// which sets window.PipelineDataPayload. Load order is enforced by the
// <script> tags in Pipeline Monitor.html.

(function () {
  const payload = window.PipelineDataPayload;
  if (!payload) {
    throw new Error('PipelineDataPayload missing — load data.sample.js (or data.local.js) before data.js');
  }

  const PROJECTS = payload.projects;

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
  const _now = Date.now();
  const WORKERS_INITIAL = payload.workers.map((w) => ({
    id: w.id,
    name: w.name,
    agent: w.agent,
    model: w.model,
    role: w.role,
    project: w.project,
    task: w.task,
    startedAt: _now - w.ageMs,
    status: 'busy',
  }));

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
        title: pick(payload.queueTitles),
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
