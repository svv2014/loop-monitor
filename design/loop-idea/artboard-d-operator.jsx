/* global React, LOOP_DATA */
// Artboard D — Operator Console
// One-screen radar for the human operator. Big metrics at top,
// queue + locks + signals across the bottom. Built for "is anything wrong?".

const { useMemo: useMemoD, useState: useStateD, useEffect: useEffectD } = React;

function DOperatorConsole() {
  const { TICKETS, LOCKS, SIGNALS, PROJECTS, EVENTS } = window.LOOP_DATA;
  const [tick, setTick] = useStateD(0);
  useEffectD(() => {
    const id = setInterval(() => setTick(t => t + 1), 2000);
    return () => clearInterval(id);
  }, []);
  const projBySlug = useMemoD(() => Object.fromEntries(PROJECTS.map(p => [p.slug, p])), []);

  const inFlight = TICKETS.filter(t => !["done"].includes(t.stage)).length;
  const blocked = TICKETS.filter(t => t.blocked || t.labels.includes("qa-fail")).length;
  const reworking = TICKETS.filter(t => t.rework).length;

  return (
    <div className="lp-frame" style={{ padding: "32px 36px", display: "flex", flexDirection: "column", gap: 18 }}>
      <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
          <span className="mono cap" style={{ fontSize: 11, color: "var(--ink-4)" }}>D · Operator Console</span>
          <h1 style={{ margin: 0, fontWeight: 500, fontSize: 28, letterSpacing: "-0.02em" }}>Loop is running.</h1>
          <span className="mono live" style={{ fontSize: 12, color: "var(--hue-pass)" }}>● healthy</span>
        </div>
        <div className="mono cap" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          host · macbook-svv · launchd · pid 41982
        </div>
      </header>

      <div className="hr" />

      {/* Big metric strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 0, borderTop: "1px solid var(--rule)", borderBottom: "1px solid var(--rule)" }}>
        <Metric n={inFlight} label="in-flight" />
        <Metric n={LOCKS.length} label="locks held" tone="dev" sep />
        <Metric n={reworking} label="rework loops" tone="review" sep />
        <Metric n={blocked} label="needs you" tone="fail" sep />
        <Metric n="13" label="merged · today" tone="pass" sep />
      </div>

      {/* 3-column body */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr", gap: 24, flex: 1, minHeight: 0 }}>
        {/* Project row */}
        <Panel title="projects · 6">
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {PROJECTS.map(p => {
              const myTickets = TICKETS.filter(t => t.proj === p.slug);
              const myStages = ["po","dev","review","qa","merge"];
              return (
                <div key={p.slug} style={{ display: "grid", gridTemplateColumns: "100px 80px 1fr", gap: 12, alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{p.name}</div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)" }}>{p.tracker.toLowerCase()} · {p.agent}</div>
                  </div>
                  <div className="mono tab" style={{ fontSize: 11, color: "var(--ink-3)" }}>{myTickets.length} open</div>
                  <div style={{ display: "flex", gap: 1, height: 14 }}>
                    {myStages.map(s => {
                      const ct = myTickets.filter(t => t.stage === s).length;
                      const tone = s === "merge" ? "pass" : s;
                      return (
                        <div key={s} style={{ flex: 1, position: "relative", background: "var(--paper-2)" }}>
                          {ct > 0 && <div className={`bg-${tone}`} style={{ position: "absolute", inset: 0, opacity: Math.min(1, 0.4 + ct * 0.18) }} />}
                          <div className="mono tab" style={{ position: "absolute", inset: 0, fontSize: 9, color: "var(--ink)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                            {ct || ""}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>

        {/* Active locks */}
        <Panel title={`active worktrees · ${LOCKS.length}`}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {LOCKS.map((l, i) => {
              const stage = l.handler.replace("-handler", "");
              const tone = stage === "merge" ? "pass" : stage === "review" ? "review" : stage === "qa" ? "qa" : "dev";
              const p = projBySlug[l.proj];
              const live = l.held > 60;
              return (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "12px 1fr auto", gap: 10, alignItems: "baseline" }}>
                  <span className={`s-${tone} dot ${live ? "live" : ""}`} />
                  <div>
                    <div className="mono" style={{ fontSize: 12 }}>
                      <span style={{ color: "var(--ink)" }}>{l.ticket}</span>
                      <span style={{ color: "var(--ink-4)" }}> · {p.name} · {stage}</span>
                    </div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)" }}>
                      {p.agent} {p.model} · /tmp/loop-locks/{l.proj}.lock
                    </div>
                  </div>
                  <span className="mono tab" style={{ fontSize: 11, color: "var(--ink-3)" }}>
                    {Math.floor(l.held/60)}m{(l.held % 60).toString().padStart(2,"0")}
                  </span>
                </div>
              );
            })}
          </div>
        </Panel>

        {/* Reconciler signals — operator attention */}
        <Panel title="signals · operator attention" tone="fail">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {SIGNALS.map((s, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                  <span className="s-fail dot-sq" />
                  <span className="cap mono" style={{ fontSize: 10, color: "var(--ink-3)" }}>{s.kind}</span>
                  <span className="mono" style={{ fontSize: 10, color: "var(--ink-4)", marginLeft: "auto" }}>{s.proj}</span>
                </div>
                <div style={{ fontSize: 12.5, color: "var(--ink)", lineHeight: 1.4, textWrap: "pretty" }}>{s.detail}</div>
              </div>
            ))}
            <div className="hr" />
            <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)", lineHeight: 1.5 }}>
              reconciler runs every 15 min · only mutators corroborate · these are observational
            </div>
          </div>
        </Panel>
      </div>

      <div className="hr" />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          last tick {(tick % 5) * 12 + 4}s ago · next tick in {280 - (tick % 60)}s
        </div>
        <div className="mono cap" style={{ fontSize: 10, color: "var(--ink-4)" }}>
          loop.env · LOOP_LOG_DIR=~/.loop/logs · LOOP_DISPATCH_MODE=direct · MAX_CONCURRENT=2
        </div>
      </div>
    </div>
  );
}

function Metric({ n, label, tone = "ink", sep }) {
  const color = tone === "ink" ? "var(--ink)" : `var(--hue-${tone})`;
  return (
    <div style={{ padding: "16px 20px", borderLeft: sep ? "1px solid var(--rule)" : "none", display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ fontSize: 44, fontWeight: 500, letterSpacing: "-0.03em", lineHeight: 1, color }}>{n}</div>
      <div className="cap mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>{label}</div>
    </div>
  );
}

function Panel({ title, tone, children }) {
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 10, minHeight: 0 }}>
      <div className="cap mono" style={{ fontSize: 11, color: tone === "fail" ? "var(--hue-fail)" : "var(--ink-3)", display: "flex", alignItems: "center", gap: 8 }}>
        {tone === "fail" && <span className="s-fail dot live" />}
        {title}
      </div>
      <div className="lp-scroll" style={{ overflowY: "auto", flex: 1 }}>
        {children}
      </div>
    </section>
  );
}

window.DOperatorConsole = DOperatorConsole;
