/* global React, LOOP_DATA */
// Artboard B — Live Stream / Event Tape
// Terminal-grade view: what is happening RIGHT NOW. Newest events at the top.
// One column for events, one for active agents. Designed to be glanceable.

const { useState: useStateB, useEffect: useEffectB, useMemo: useMemoB } = React;

function fmtAgo(s) {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s/60)}m`;
  return `${Math.floor(s/3600)}h${Math.floor((s%3600)/60).toString().padStart(2,"0")}`;
}

function BLiveStream() {
  const { EVENTS, LOCKS, PROJECTS } = window.LOOP_DATA;
  const [tick, setTick] = useStateB(0);
  useEffectB(() => {
    const id = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const projBySlug = useMemoB(() => Object.fromEntries(PROJECTS.map(p => [p.slug, p])), []);

  return (
    <div className="lp-frame" style={{ padding: "32px 36px", display: "flex", flexDirection: "column", gap: 18 }}>
      <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
          <span className="mono cap" style={{ fontSize: 11, color: "var(--ink-4)" }}>B · Live Stream</span>
          <h1 style={{ margin: 0, fontWeight: 500, fontSize: 28, letterSpacing: "-0.02em" }}>What's happening</h1>
        </div>
        <div className="mono cap" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          <span className="dot live s-pass" style={{ marginRight: 6 }} />
          live · {16 + (tick % 4)} events past hour
        </div>
      </header>

      <div className="hr" />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 24, flex: 1, minHeight: 0 }}>
        {/* Event tape */}
        <div style={{ display: "flex", flexDirection: "column", gap: 0, minHeight: 0 }}>
          <div className="cap mono" style={{ fontSize: 11, color: "var(--ink-3)", paddingBottom: 8 }}>
            event tape · scanner→handler→agent→label
          </div>
          <div className="lp-scroll mono" style={{ fontSize: 12.5, lineHeight: 1.6, overflowY: "auto", flex: 1, paddingRight: 8 }}>
            {EVENTS.map((e, i) => {
              const proj = e.proj ? projBySlug[e.proj] : null;
              return (
                <div key={i} style={{
                  display: "grid",
                  gridTemplateColumns: "44px 92px 70px 1fr",
                  gap: 12,
                  padding: "5px 0",
                  borderTop: i === 0 ? "none" : "1px dashed var(--rule)",
                  alignItems: "baseline",
                }}>
                  <span style={{ color: "var(--ink-4)" }}>{fmtAgo(e.t)}</span>
                  <span style={{ color: "var(--ink-3)" }}>{e.type}</span>
                  <span className={`s-${e.color}`} style={{ fontWeight: 500 }}>
                    {e.ticket || (e.handler === "scanner" ? "—" : e.handler)}
                  </span>
                  <span>
                    {proj && <span style={{ color: "var(--ink-3)", marginRight: 8 }}>{proj.name}</span>}
                    <span style={{ color: "var(--ink)" }}>{e.msg}</span>
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Active agents column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, minHeight: 0, borderLeft: "1px solid var(--rule)", paddingLeft: 24 }}>
          <div className="cap mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>
            agents in-flight · {LOCKS.length}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {LOCKS.map((l, i) => {
              const p = projBySlug[l.proj];
              const stage = l.handler.replace("-handler", "");
              const stageColor = stage === "merge" ? "pass" : stage === "rework" ? "fail" : stage === "review" ? "review" : stage === "qa" ? "qa" : "dev";
              const max = 2400;
              const pct = Math.min(100, (l.held / max) * 100);
              return (
                <div key={i} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                    <span className={`dot live s-${stageColor}`} />
                    <span className="mono" style={{ fontSize: 12 }}>{l.ticket}</span>
                    <span className="mono" style={{ fontSize: 10, color: "var(--ink-4)", marginLeft: "auto" }}>{fmtAgo(l.held)}</span>
                  </div>
                  <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
                    {p.name} · {p.agent} {p.model} · {stage}
                  </div>
                  <div style={{ height: 2, background: "var(--rule)", position: "relative" }}>
                    <div className={`bg-${stageColor}`} style={{ position: "absolute", left: 0, top: 0, height: 2, width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="hr" style={{ marginTop: "auto" }} />
          <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)", display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>scanner</span><span className="tab">tick · 2:14</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>reconciler</span><span className="tab">tick · 9:42</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>pipeline_slots</span><span className="tab">6 / 8 used</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.BLiveStream = BLiveStream;
