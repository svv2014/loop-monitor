// Shared mock data for all artboards. Models Loop's actual state machine.
// (po → dev → review → qa → merge, with rework, blocked, qa-fail edges)

window.LOOP_DATA = (() => {
  const STAGES = [
    { id: "po",     label: "needs-po",     handler: "po-handler" },
    { id: "dev",    label: "needs-dev",    handler: "dev-handler" },
    { id: "review", label: "needs-review", handler: "review-handler" },
    { id: "qa",     label: "needs-qa",     handler: "qa-handler" },
    { id: "merge",  label: "qa-pass",      handler: "merge-handler" },
    { id: "done",   label: "done",         handler: null },
  ];

  const PROJECTS = [
    { slug: "navi",       name: "navi-app",            backend: "github",      repo: "acme/navi-app",        agent: "claude",  model: "sonnet",      tracker: "GitHub" },
    { slug: "ledger",     name: "ledger-api",          backend: "gitlab",      repo: "acme/ledger-api",      agent: "codex",   model: "o4-mini",     tracker: "GitLab" },
    { slug: "atlas",      name: "atlas-web",           backend: "github",      repo: "acme/atlas-web",       agent: "claude",  model: "opus",        tracker: "Linear" },
    { slug: "kestrel",    name: "kestrel-pipeline",    backend: "jira-gitlab", repo: "acme/kestrel",         agent: "gemini",  model: "2.5-pro",     tracker: "Jira" },
    { slug: "wolfpack",   name: "wolfpack-cli",        backend: "github",      repo: "acme/wolfpack-cli",    agent: "aider",   model: "sonnet",      tracker: "GitHub" },
    { slug: "drift",      name: "drift-docs",          backend: "github",      repo: "acme/drift-docs",      agent: "claude",  model: "haiku",       tracker: "Shortcut" },
  ];

  // tickets — current state of each
  const TICKETS = [
    { id: "NAV-241",  proj: "navi",     title: "Refresh empty-state for /reports",                 stage: "po",     waiting: 3,  prio: "med", labels: ["needs-po"] },
    { id: "NAV-238",  proj: "navi",     title: "Fix calendar week-rollover off-by-one",            stage: "dev",    waiting: 7,  prio: "high",labels: ["in-dev"], runtime: 412, agent: "claude" },
    { id: "NAV-235",  proj: "navi",     title: "Inline edits for filter chips",                    stage: "review", waiting: 2,  prio: "med", labels: ["in-review"], runtime: 38, agent: "claude" },
    { id: "NAV-232",  proj: "navi",     title: "Pagination cursor leaks into URL hash",            stage: "qa",     waiting: 1,  prio: "high",labels: ["in-qa"], runtime: 92, agent: "claude" },
    { id: "NAV-228",  proj: "navi",     title: "Localize date headers (es, fr, ja)",               stage: "merge",  waiting: 0,  prio: "low", labels: ["qa-pass"] },

    { id: "LED-1108", proj: "ledger",   title: "Reconcile decimal precision on FX writes",         stage: "dev",    waiting: 12, prio: "high",labels: ["in-dev"], runtime: 711, agent: "codex" },
    { id: "LED-1104", proj: "ledger",   title: "POST /transfers idempotency-key validation",       stage: "review", waiting: 4,  prio: "high",labels: ["needs-review"] },
    { id: "LED-1099", proj: "ledger",   title: "Audit-log retention to 36 months",                 stage: "qa",     waiting: 2,  prio: "med", labels: ["needs-qa"] },
    { id: "LED-1093", proj: "ledger",   title: "Fix flaky bats test for nested ledgers",           stage: "dev",    waiting: 27, prio: "low", labels: ["in-rework"], runtime: 240, agent: "codex", rework: 2 },

    { id: "ATL-72",   proj: "atlas",    title: "Map clusters jitter on zoom",                      stage: "po",     waiting: 1,  prio: "med", labels: ["needs-po"] },
    { id: "ATL-69",   proj: "atlas",    title: "Side panel keyboard nav for screenreaders",        stage: "review", waiting: 5,  prio: "high",labels: ["in-review"], runtime: 16, agent: "claude" },
    { id: "ATL-64",   proj: "atlas",    title: "Bundle size +14kb regression",                     stage: "qa",     waiting: 8,  prio: "high",labels: ["qa-fail"], rework: 1 },

    { id: "KES-411",  proj: "kestrel",  title: "Stream parser drops final chunk on EOF",           stage: "dev",    waiting: 33, prio: "high",labels: ["in-dev"], runtime: 1840, agent: "gemini" },
    { id: "KES-405",  proj: "kestrel",  title: "Backoff on 429 from upstream provider",            stage: "merge",  waiting: 0,  prio: "med", labels: ["qa-pass"] },
    { id: "KES-398",  proj: "kestrel",  title: "Pipeline DAG visualizer renders blank on Safari",  stage: "po",     waiting: 9,  prio: "med", labels: ["blocked"], blocked: true },

    { id: "WLF-22",   proj: "wolfpack", title: "Add --json output to `loop status`",               stage: "review", waiting: 1,  prio: "med", labels: ["needs-review"] },
    { id: "WLF-19",   proj: "wolfpack", title: "Self-update gate breaks on minor.patch jumps",     stage: "dev",    waiting: 6,  prio: "high",labels: ["in-dev"], runtime: 522, agent: "aider" },

    { id: "DRF-58",   proj: "drift",    title: "Migrate ASCII flow diagram to mermaid",            stage: "review", waiting: 0,  prio: "low", labels: ["needs-review"] },
    { id: "DRF-55",   proj: "drift",    title: "Quick-start: collapse advanced section",           stage: "merge",  waiting: 0,  prio: "low", labels: ["qa-pass"] },
  ];

  // Live event tape — what has happened in the last hour, newest first.
  // Each event references a handler emit + label flip.
  const EVENTS = [
    { t: 5,    type: "lock.release", proj: "navi",     ticket: "NAV-235", handler: "review-handler", msg: "approve → needs-qa", color: "review" },
    { t: 18,   type: "agent.write",  proj: "kestrel",  ticket: "KES-411", handler: "dev-handler",    msg: "patch +124 −28 across 6 files", color: "dev" },
    { t: 31,   type: "label.flip",   proj: "ledger",   ticket: "LED-1093",handler: "dev-rework",     msg: "qa-fail → in-rework (#2)", color: "fail" },
    { t: 47,   type: "scanner.tick", proj: null,       ticket: null,      handler: "scanner",        msg: "tick — 6 projects polled", color: "idle" },
    { t: 62,   type: "lock.acquire", proj: "ledger",   ticket: "LED-1108",handler: "dev-handler",    msg: "lock /tmp/loop-locks/ledger.lock", color: "dev" },
    { t: 84,   type: "agent.spawn",  proj: "ledger",   ticket: "LED-1108",handler: "dev-handler",    msg: "codex o4-mini · worktree-1108", color: "dev" },
    { t: 110,  type: "merge.done",   proj: "kestrel",  ticket: "KES-405", handler: "merge-handler",  msg: "squash-merge · closed #405 · +13 pts", color: "pass" },
    { t: 138,  type: "qa.pass",      proj: "kestrel",  ticket: "KES-405", handler: "qa-handler",     msg: "AC 4/4 · regression 0/0 fail · validation_cmd ok", color: "pass" },
    { t: 165,  type: "qa.fail",      proj: "atlas",    ticket: "ATL-64",  handler: "qa-handler",     msg: "bundle-size budget exceeded by 14.2kb", color: "fail" },
    { t: 191,  type: "review.req",   proj: "atlas",    ticket: "ATL-69",  handler: "review-handler", msg: "AI reviewer · request changes · 3 nits", color: "review" },
    { t: 220,  type: "po.expand",    proj: "navi",     ticket: "NAV-241", handler: "po-handler",     msg: "spec expanded · 6 ACs · est S", color: "po" },
    { t: 244,  type: "reconciler",   proj: null,       ticket: null,      handler: "reconciler",     msg: "alias rename · po-review→needs-po · 2 issues", color: "idle" },
    { t: 271,  type: "scanner.tick", proj: null,       ticket: null,      handler: "scanner",        msg: "tick — 6 projects polled", color: "idle" },
    { t: 304,  type: "agent.write",  proj: "wolfpack", ticket: "WLF-19",  handler: "dev-handler",    msg: "patch +44 −12 across 2 files", color: "dev" },
    { t: 339,  type: "blocked",      proj: "kestrel",  ticket: "KES-398", handler: "dev-handler",    msg: "3 retries exceeded · → blocked", color: "fail" },
    { t: 360,  type: "judge.post",   proj: "kestrel",  ticket: "KES-405", handler: "judge",          msg: "scorecard posted · 89/100 · clean merge", color: "pass" },
  ];

  // Reconciler observational signals
  const SIGNALS = [
    { kind: "lost-issue",   proj: "atlas",   detail: "ATL-71 has no pipeline label · 26h cool-down" },
    { kind: "anomaly",      proj: "ledger",  detail: "LED-1093 touched 4× in 1h — possible rework loop" },
    { kind: "agent-distress",proj:"kestrel", detail: "‘reconciler keeps reverting’ · KES-411 comment" },
  ];

  // Locks & queue
  const LOCKS = [
    { proj: "navi",     ticket: "NAV-238", handler: "dev-handler",    held: 412 },
    { proj: "ledger",   ticket: "LED-1108",handler: "dev-handler",    held: 711 },
    { proj: "kestrel",  ticket: "KES-411", handler: "dev-handler",    held: 1840 },
    { proj: "wolfpack", ticket: "WLF-19",  handler: "dev-handler",    held: 522 },
    { proj: "navi",     ticket: "NAV-232", handler: "qa-handler",     held: 92 },
    { proj: "atlas",    ticket: "ATL-69",  handler: "review-handler", held: 16 },
  ];

  return { STAGES, PROJECTS, TICKETS, EVENTS, SIGNALS, LOCKS };
})();
