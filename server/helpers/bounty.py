from server.models import ReportPayload

BOUNTY_POINTS = {
    "dev_done":     3,
    "rework_done":  2,
    "review_done":  2,
    "merge_done":   2,
    "po_done":      2,
    "qa_pass":      1,
    "qa_done":      1,
    "dev_failed":  -1,
    "rework_failed": -1,
    "review_failed": -1,
    "po_failed":   -1,
}


def auto_bounty(conn, data: ReportPayload, now: str):
    """Auto-insert a verdict when a terminal event is received."""
    pts = BOUNTY_POINTS.get(data.event_type)
    if pts is None:
        return
    reason = f"auto: {data.event_type}"
    if data.issue_number:
        reason += f" issue #{data.issue_number}"
    elif data.pr_number:
        reason += f" PR #{data.pr_number}"
    conn.execute(
        "INSERT INTO verdicts (project, role, model, points, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (data.project, data.role, data.model, pts, reason, now),
    )
    existing = conn.execute(
        "SELECT id, total_points, verdict_count FROM scores WHERE project=? AND role=? AND model IS ?",
        (data.project, data.role, data.model),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE scores SET total_points=?, verdict_count=?, updated_at=? WHERE id=?",
            (existing["total_points"] + pts, existing["verdict_count"] + 1, now, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO scores (project, role, model, total_points, verdict_count, updated_at)"
            " VALUES (?, ?, ?, ?, 1, ?)",
            (data.project, data.role, data.model, pts, now),
        )
