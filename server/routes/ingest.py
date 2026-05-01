import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException

from server.constants import MONITOR_VERSION, SUPPORTED_API_MAJOR
from server.db import get_db
from server.helpers.bounty import auto_bounty
from server.models import ReportPayload, VerdictPayload

router = APIRouter()
logger = logging.getLogger(__name__)


def _insert_event(data: ReportPayload):
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO events
           (project, role, model, event_type, issue_number, pr_number, detail, payload,
            core_version, loop_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.project,
            data.role,
            data.model,
            data.event_type,
            data.issue_number,
            data.pr_number,
            data.detail,
            json.dumps(data.payload) if data.payload else None,
            data.core_version,
            data.loop_id,
            now,
        ),
    )

    if data.issue_number is not None:
        conn.execute(
            """INSERT INTO issue_history
               (project, issue_number, pr_number, role, event_type, agent, model,
                duration_seconds, rework_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.project,
                data.issue_number,
                data.pr_number,
                data.role,
                data.event_type,
                data.agent,
                data.model,
                data.duration_seconds,
                data.rework_count or 0,
                now,
            ),
        )

        existing_run = conn.execute(
            "SELECT id, rework_count FROM pipeline_runs WHERE project=? AND issue_number=?",
            (data.project, data.issue_number),
        ).fetchone()

        if existing_run:
            updates = ["completed_at=?"]
            params: list = [now]
            if data.pr_number is not None:
                updates.append("pr_number=?")
                params.append(data.pr_number)
            if data.rework_count is not None:
                updates.append("rework_count=rework_count+?")
                params.append(data.rework_count)
            params.append(existing_run["id"])
            conn.execute(
                f"UPDATE pipeline_runs SET {', '.join(updates)} WHERE id=?",
                params,
            )
        else:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (project, issue_number, pr_number, started_at, completed_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (data.project, data.issue_number, data.pr_number, now, now, now),
            )

    if data.event_type == "finished" and data.issue_number is not None:
        now_dt = datetime.fromisoformat(now)
        run = conn.execute(
            "SELECT id, started_at FROM pipeline_runs WHERE project=? AND issue_number=? ORDER BY id DESC LIMIT 1",
            (data.project, data.issue_number),
        ).fetchone()
        if run:
            try:
                started = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
                issue_secs = int((now_dt - started).total_seconds())
            except Exception:
                issue_secs = None
            first_pr = conn.execute(
                "SELECT created_at FROM issue_history"
                " WHERE project=? AND issue_number=? AND pr_number IS NOT NULL"
                " ORDER BY id ASC LIMIT 1",
                (data.project, data.issue_number),
            ).fetchone()
            pr_secs = None
            if first_pr:
                try:
                    pr_start = datetime.fromisoformat(first_pr["created_at"].replace("Z", "+00:00"))
                    pr_secs = int((now_dt - pr_start).total_seconds())
                except Exception:
                    pass
            conn.execute(
                """UPDATE pipeline_runs SET outcome=?, completed_at=?, issue_lifetime_seconds=?, pr_lifetime_seconds=?
                   WHERE id=?""",
                (data.detail or "finished", now, issue_secs, pr_secs, run["id"]),
            )

    auto_bounty(conn, data, now)
    conn.commit()
    conn.close()


def _insert_verdict(data: VerdictPayload):
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO verdicts (project, role, model, points, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (data.project, data.role, data.model, data.points, data.reason, now),
    )
    existing = conn.execute(
        "SELECT id, total_points, verdict_count FROM scores WHERE project=? AND role=? AND model IS ?",
        (data.project, data.role, data.model),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE scores SET total_points=?, verdict_count=?, updated_at=? WHERE id=?",
            (
                existing["total_points"] + data.points,
                existing["verdict_count"] + 1,
                now,
                existing["id"],
            ),
        )
    else:
        conn.execute(
            "INSERT INTO scores (project, role, model, total_points, verdict_count, updated_at)"
            " VALUES (?, ?, ?, ?, 1, ?)",
            (data.project, data.role, data.model, data.points, now),
        )
    conn.commit()
    conn.close()


@router.post("/api/report", status_code=202)
async def report(data: ReportPayload, background_tasks: BackgroundTasks):
    if not data.api:
        logger.warning("Received bounty event with no 'api' field — treating as v1.0 legacy")
    # Bounty event API version negotiation: accept 1.x, reject other majors with 426.
    if data.api:
        major = data.api.split(".", 1)[0]
        if major != SUPPORTED_API_MAJOR:
            raise HTTPException(
                status_code=426,
                detail={
                    "error": "version_unsupported",
                    "supported": [f"{SUPPORTED_API_MAJOR}.x"],
                    "received": data.api,
                },
            )
    background_tasks.add_task(_insert_event, data)
    return {"status": "accepted", "monitor_version": MONITOR_VERSION}


@router.post("/api/verdict", status_code=202)
async def verdict(data: VerdictPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(_insert_verdict, data)
    return {"status": "accepted"}
