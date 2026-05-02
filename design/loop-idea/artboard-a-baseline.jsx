/* global React, LOOP_DATA */
// Artboard A — Baseline Pipeline Monitor (the "current" reference, polished)
// Straight kanban-style view of the label state machine across all projects.

const { useState, useMemo } = React;

function ABaseline({ density = "comfy" }) {
  const { STAGES, TICKETS, PROJECTS } = window.LOOP_DATA;
  const stages = STAGES.filter(s => s.id !== "done");
  const projBySlug = useMemo(() => Object.fromEntries(PROJECTS.map(p => [p.slug, p])), []);
  const byStage = useMemo(() => {
    const m = {};
    for (const s of stages) m[s.id] = [];
    for (const t of TICKETS) (m[t.stage] = m[t.stage] || []).push(t);
    return m;
  }, []);

  const rowH = density === "dense" ? 26 : 36;

  return (
    <div className="lp-frame" style={{ padding: "32px 36px", display: "flex", flexDirection: "column", gap: 18 }}>
      <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
          <span className="mono cap" style={{ fontSize: 11, color: "var(--ink-4)" }}>A · Baseline</span>
          <h1 style={{ margin: 0, fontWeight: 500, fontSize: 28, letterSpacing: "-0.02em" }}>Pipeline</h1>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>6 projects · 19 in-flight</span>
        </div>
        <div className="mono cap" style={{ fontSize: 11, color: "var(--ink-4)" }}>
          scanner · next tick in <span style={{ color: "var(--ink) " }}>2:14</span>
        </div>
      </header>

      <div className="hr" />

      {/* Column headers */}
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${stages.length}, 1fr)`, gap: 16 }}>
        {stages.map(s => (
          <div key={s.id} style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span className={`s-${s.id === "merge" ? "pass" : s.id} dot`} />
            <span className="cap mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>{s.label}</span>
            <span className="mono tab" style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-4)" }}>
              {String(byStage[s.id].length).padStart(2, "0")}
            </span>
          </div>
        ))}
      </div>

      {/* Cards grid */}
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${stages.length}, 1fr)`, gap: 16, flex: 1, minHeight: 0 }}>
        {stages.map(s => (
          <div key={s.id} className="lp-scroll" style={{ display: "flex", flexDirection: "column", gap: 8, overflowY: "auto", paddingRight: 4 }}>
            {byStage[s.id].map(t => {
              const p = projBySlug[t.proj];
              const isLive = t.labels.some(l => l.startsWith("in-"));
              const isFail = t.labels.includes("qa-fail") || t.blocked;
              return (
                <div key={t.id} style={{
                  background: "var(--paper-2)",
                  border: `1px solid ${isFail ? "var(--hue-fail)" : "var(--rule)"}`,
                  padding: density === "dense" ? "8px 10px" : "12px 12px",
                  display: "flex", flexDirection: "column", gap: 6,
                  minHeight: rowH,
                }}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                    <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>{t.id}</span>
                    {isLive && <span className={`s-${s.id} live`} style={{ fontSize: 10 }}>●</span>}
                    {t.rework && <span className="mono" style={{ fontSize: 10, color: "var(--hue-fail)" }}>↻{t.rework}</span>}
                    <span className="mono tab" style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-4)" }}>
                      {t.waiting > 0 ? `${t.waiting}m` : "—"}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, lineHeight: 1.35, color: "var(--ink)", textWrap: "pretty" }}>
                    {t.title}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
                    <span className="mono cap" style={{ fontSize: 10, color: "var(--ink-3)" }}>{p.tracker}</span>
                    <span style={{ width: 1, height: 9, background: "var(--rule)" }} />
                    <span className="mono" style={{ fontSize: 10, color: "var(--ink-3)" }}>{p.name}</span>
                    {t.agent && <>
                      <span style={{ width: 1, height: 9, background: "var(--rule)" }} />
                      <span className="mono" style={{ fontSize: 10, color: "var(--ink-3)" }}>{t.agent}</span>
                    </>}
                  </div>
                </div>
              );
            })}
            {byStage[s.id].length === 0 && (
              <div className="mono" style={{ fontSize: 11, color: "var(--ink-4)", padding: "8px 0" }}>—</div>
            )}
          </div>
        ))}
      </div>

      {/* Footer ticker */}
      <div className="hr" />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          <span style={{ color: "var(--accent)" }}>●</span> 6 locks held · reconciler in 9:42 · 3 signals
        </div>
        <div className="mono cap" style={{ fontSize: 10, color: "var(--ink-4)" }}>
          loop v0.2.0 · LOOP_AGENT=claude · dispatch=direct
        </div>
      </div>
    </div>
  );
}

window.ABaseline = ABaseline;
