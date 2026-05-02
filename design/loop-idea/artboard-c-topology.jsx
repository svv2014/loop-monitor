/* global React, LOOP_DATA */
// Artboard C — Pipeline Topology
// Loop as a *bridge* between trackers (Jira/Linear/GitHub/GitLab/Shortcut)
// and outcomes. Center column is Loop's stage machine; sides show source
// trackers (left) and destination repos / outcomes (right).
// This is the differentiator artboard — Loop sits between the two.

const { useMemo: useMemoC } = React;

function CTopology() {
  const { TICKETS, PROJECTS, STAGES } = window.LOOP_DATA;
  const projBySlug = useMemoC(() => Object.fromEntries(PROJECTS.map(p => [p.slug, p])), []);

  // Group tickets by source tracker
  const trackerGroups = useMemoC(() => {
    const groups = {};
    for (const t of TICKETS) {
      const tracker = projBySlug[t.proj].tracker;
      (groups[tracker] = groups[tracker] || []).push(t);
    }
    return groups;
  }, []);

  const stages = STAGES.filter(s => s.id !== "done");

  // Throughput per stage (made up but plausible from data)
  const flow = useMemoC(() => {
    const counts = {};
    for (const s of stages) counts[s.id] = TICKETS.filter(t => t.stage === s.id).length;
    return counts;
  }, []);

  return (
    <div className="lp-frame" style={{ padding: "32px 36px", display: "flex", flexDirection: "column", gap: 18 }}>
      <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
          <span className="mono cap" style={{ fontSize: 11, color: "var(--ink-4)" }}>C · Topology</span>
          <h1 style={{ margin: 0, fontWeight: 500, fontSize: 28, letterSpacing: "-0.02em" }}>Trackers → Loop → Ship</h1>
        </div>
        <div className="mono cap" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          you orchestrate the orchestrators
        </div>
      </header>

      <div className="hr" />

      <div style={{ display: "grid", gridTemplateColumns: "200px 1fr 200px", gap: 0, flex: 1, minHeight: 0 }}>
        {/* LEFT — Source trackers */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingRight: 12, borderRight: "1px solid var(--rule)" }}>
          <div className="cap mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>sources</div>
          {Object.entries(trackerGroups).map(([tr, ts]) => (
            <div key={tr} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
                <span style={{ fontSize: 14, fontWeight: 500 }}>{tr}</span>
                <span className="mono tab" style={{ fontSize: 11, color: "var(--ink-4)" }}>{ts.length}</span>
              </div>
              <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
                {[...new Set(ts.map(t => projBySlug[t.proj].name))].join(" · ")}
              </div>
              <div style={{ display: "flex", gap: 2, marginTop: 4 }}>
                {ts.map((t, i) => (
                  <span key={i}
                    title={t.id}
                    className={`bg-${t.stage === "merge" ? "pass" : t.stage}`}
                    style={{ width: 10, height: 10, opacity: t.blocked ? 0.4 : 0.85 }} />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* CENTER — Loop pipeline diagram (SVG) */}
        <div style={{ position: "relative", overflow: "hidden", padding: "0 24px" }}>
          <CenterDiagram stages={stages} flow={flow} />
        </div>

        {/* RIGHT — Destinations / outcomes */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingLeft: 12, borderLeft: "1px solid var(--rule)" }}>
          <div className="cap mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>this hour</div>
          <Outcome label="merged" big="3" sub="navi · kestrel · drift" tone="pass" />
          <Outcome label="opened PR" big="5" sub="dev-handler · fresh worktrees" tone="dev" />
          <Outcome label="qa-fail" big="2" sub="ATL-64 · LED-1093 (rework #2)" tone="fail" />
          <Outcome label="blocked" big="1" sub="KES-398 · 3 retries" tone="fail" />
          <Outcome label="agent-distress" big="1" sub="kestrel · narrative-pathology" tone="review" />
        </div>
      </div>

      <div className="hr" />
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          all flow is label-driven · Loop never owns the ticket, just moves it
        </div>
        <div className="mono cap" style={{ fontSize: 10, color: "var(--ink-4)" }}>
          adapters: github · gitlab · jira-gitlab · ext: linear · shortcut
        </div>
      </div>
    </div>
  );
}

function Outcome({ label, big, sub, tone }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span className={`s-${tone} dot-sq`} />
        <span className="cap mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>{label}</span>
      </div>
      <div style={{ fontSize: 32, fontWeight: 500, letterSpacing: "-0.03em", lineHeight: 1 }}>{big}</div>
      <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)" }}>{sub}</div>
    </div>
  );
}

function CenterDiagram({ stages, flow }) {
  const W = 720, H = 480;
  // 5 stages laid out vertically — flow top-down
  const padY = 40, padX = 60;
  const stepH = (H - padY * 2) / (stages.length - 1);
  const xCenter = W / 2;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "100%" }}>
      <defs>
        <pattern id="stripes" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--rule)" strokeWidth="1" />
        </pattern>
      </defs>

      {/* outer frame */}
      <rect x="40" y="20" width={W - 80} height={H - 40} fill="none" stroke="var(--rule)" />
      <text x={W/2} y="14" textAnchor="middle" className="mono cap" fontSize="10" fill="var(--ink-3)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
        loop pipeline · label state machine
      </text>

      {/* trunk line */}
      <line x1={xCenter} y1={padY} x2={xCenter} y2={H - padY} stroke="var(--ink-3)" strokeWidth="1" />

      {stages.map((s, i) => {
        const y = padY + i * stepH;
        const tone = s.id === "merge" ? "pass" : s.id;
        const count = flow[s.id];
        const w = 28 + count * 22;
        return (
          <g key={s.id}>
            {/* node bar — width encodes throughput */}
            <rect x={xCenter - w/2} y={y - 14} width={w} height={28} fill="var(--paper-2)" stroke={`var(--hue-${tone})`} />
            {/* label inside */}
            <text x={xCenter} y={y + 4} textAnchor="middle" className="mono" fontSize="11" fill="var(--ink)">
              {s.label}
            </text>

            {/* left arm — count */}
            <text x={xCenter - w/2 - 12} y={y + 4} textAnchor="end" className="mono tab" fontSize="11" fill="var(--ink-3)">
              {String(count).padStart(2, "0")}
            </text>
            {/* right arm — handler */}
            <text x={xCenter + w/2 + 12} y={y + 4} textAnchor="start" className="mono" fontSize="10" fill="var(--ink-4)">
              {s.handler}
            </text>

            {/* rework arrow back to dev (between review/qa and dev) */}
            {(s.id === "review" || s.id === "qa") && (
              <g>
                <path
                  d={`M ${xCenter - w/2 - 8} ${y} Q ${padX + 30} ${y} ${padX + 30} ${(padY + stepH) - 10} L ${xCenter - 30} ${padY + stepH}`}
                  fill="none" stroke="var(--hue-fail)" strokeWidth="1" strokeDasharray="3 3" opacity="0.55" />
                <text x={padX + 36} y={(y + padY + stepH)/2} className="mono cap" fontSize="9" fill="var(--hue-fail)">
                  rework
                </text>
              </g>
            )}
          </g>
        );
      })}

      {/* terminal: done */}
      <circle cx={xCenter} cy={H - padY + 22} r="6" fill="var(--hue-pass)" />
      <text x={xCenter + 14} y={H - padY + 26} className="mono cap" fontSize="10" fill="var(--ink-3)">
        done · close issue · bounty +N
      </text>

      {/* entry: po-review / dev */}
      <text x={xCenter} y={padY - 18} textAnchor="middle" className="mono cap" fontSize="9" fill="var(--ink-4)">
        operator labels issue
      </text>
      <line x1={xCenter} y1={padY - 14} x2={xCenter} y2={padY - 14 + 8} stroke="var(--ink-3)" />
    </svg>
  );
}

window.CTopology = CTopology;
