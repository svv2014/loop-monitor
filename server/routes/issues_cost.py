import json
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends

from server.constants import PROJECTS
from server.db import db_dep

router = APIRouter()

# (project, issue_number) -> (expiry_timestamp, meta_dict)
_gh_cache: dict[tuple[str, int], tuple[float, dict]] = {}
_GH_TTL = 60

_PRIORITY_LABELS = {"p0-critical", "p1-high", "p2-medium", "p3-low"}
_ROLES = ["po", "dev", "review", "qa", "merge"]
_CHILD_RE = re.compile(r"(?:closes|depends\s+on)\s+#(\d+)", re.IGNORECASE)


def _fetch_gh_meta(project: str, issue_number: int) -> dict:
    key = (project, issue_number)
    now = datetime.now(timezone.utc).timestamp()
    if key in _gh_cache:
        expiry, data = _gh_cache[key]
        if now < expiry:
            return data

    default: dict = {"title": "", "state": "unknown", "priority": None, "body": "", "merged": False}
    repo = PROJECTS.get(project)
    if not repo:
        _gh_cache[key] = (now + _GH_TTL, default)
        return default
    try:
        result = subprocess.run(
            [
                "gh", "api",
                f"repos/{repo}/issues/{issue_number}",
                "--jq",
                "{title, state, body, labels: [.labels[].name], pull_request}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            _gh_cache[key] = (now + _GH_TTL, default)
            return default
        raw = json.loads(result.stdout)
        labels: list[str] = raw.get("labels") or []
        priority: Optional[str] = next((lbl for lbl in labels if lbl in _PRIORITY_LABELS), None)
        pr_field = raw.get("pull_request") or {}
        merged = bool(pr_field.get("merged_at"))
        meta: dict = {
            "title": raw.get("title") or "",
            "state": raw.get("state") or "unknown",
            "priority": priority,
            "body": raw.get("body") or "",
            "merged": merged,
        }
        _gh_cache[key] = (now + _GH_TTL, meta)
        return meta
    except Exception:
        _gh_cache[key] = (now + _GH_TTL, default)
        return default


def _parse_children(body: str) -> int:
    return len(set(_CHILD_RE.findall(body)))


def _build_row(raw: dict, meta: dict, now_ts: float) -> dict:
    actual_runs: int = raw.get("actual_runs") or 0
    child_count = _parse_children(meta.get("body") or "")
    happy_path_runs = 5 + (5 * child_count)
    rework_factor = 0.0 if actual_runs == 0 else round(actual_runs / happy_path_runs, 2)

    state: str = meta.get("state") or "unknown"
    merged: bool = meta.get("merged") or False
    stranded_seconds: Optional[int] = None
    if state == "open" and not merged:
        last_event: Optional[str] = raw.get("last_event")
        if last_event:
            try:
                last_dt = datetime.fromisoformat(last_event.replace(" ", "T"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                stranded_seconds = int(now_ts - last_dt.timestamp())
            except Exception:
                pass

    stage_runs: dict = {}
    for role in _ROLES:
        stage_runs[role] = raw.get(f"{role}_runs") or 0
        stage_runs[f"{role}_failed"] = raw.get(f"{role}_failed") or 0

    project = raw["project"]
    repo = PROJECTS.get(project)
    github_url = (
        f"https://github.com/{repo}/issues/{raw['issue_number']}"
        if repo else None
    )

    return {
        "project": project,
        "issue_number": raw["issue_number"],
        "title": meta.get("title") or "",
        "priority": meta.get("priority"),
        "state": state,
        "first_event": raw.get("first_event"),
        "last_event": raw.get("last_event"),
        "stage_runs": stage_runs,
        "happy_path_runs": happy_path_runs,
        "actual_runs": actual_runs,
        "rework_factor": rework_factor,
        "total_points": raw.get("total_points") or 0,
        "verdict_count": raw.get("verdict_count") or 0,
        "stranded_seconds": stranded_seconds,
        "github_url": github_url,
    }


_REWORK_EVENT_TYPES = ("po_failed", "dev_failed", "dev_rework", "qa_failed", "review_failed")


@router.get("/api/issues/cost")
def get_issues_cost(
    project: Optional[str] = None,
    since: Optional[str] = None,
    day: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    conn: sqlite3.Connection = Depends(db_dep),
) -> list:
    if day is not None:
        # Filter to issues that had rework events on a specific date (YYYY-MM-DD)
        since_iso = f"{day}T00:00:00+00:00"
        until_iso = f"{day}T23:59:59+00:00"
    elif since is None:
        since_dt = datetime.now(timezone.utc) - timedelta(days=30)
        since_iso = since_dt.isoformat()
        until_iso = None
    else:
        since_iso = since
        until_iso = None

    project_param: Optional[str] = project

    rework_types_ph = ",".join("?" * len(_REWORK_EVENT_TYPES))

    if day is not None:
        # Filter to issues that had rework events on the specified day;
        # aggregate their full history so actual_runs reflects total pipeline runs.
        params_day = [since_iso, until_iso, project_param, project_param, *_REWORK_EVENT_TYPES, limit, offset]
        rows = conn.execute(
            f"""
            WITH rework_issues AS (
                SELECT DISTINCT project, issue_number
                FROM events
                WHERE issue_number IS NOT NULL
                  AND created_at >= ?
                  AND created_at <= ?
                  AND (? IS NULL OR project = ?)
                  AND event_type IN ({rework_types_ph})
            ),
            agg AS (
                SELECT
                    e.project,
                    e.issue_number,
                    MIN(e.created_at)                                                    AS first_event,
                    MAX(e.created_at)                                                    AS last_event,
                    SUM(CASE WHEN e.event_type LIKE '%_start'   THEN 1 ELSE 0 END)      AS actual_runs,
                    SUM(CASE WHEN e.event_type = 'po_start'     THEN 1 ELSE 0 END)      AS po_runs,
                    SUM(CASE WHEN e.event_type = 'po_failed'    THEN 1 ELSE 0 END)      AS po_failed,
                    SUM(CASE WHEN e.event_type = 'dev_start'    THEN 1 ELSE 0 END)      AS dev_runs,
                    SUM(CASE WHEN e.event_type = 'dev_failed'   THEN 1 ELSE 0 END)      AS dev_failed,
                    SUM(CASE WHEN e.event_type = 'review_start' THEN 1 ELSE 0 END)      AS review_runs,
                    SUM(CASE WHEN e.event_type = 'review_failed' THEN 1 ELSE 0 END)     AS review_failed,
                    SUM(CASE WHEN e.event_type = 'qa_start'     THEN 1 ELSE 0 END)      AS qa_runs,
                    SUM(CASE WHEN e.event_type = 'qa_failed'    THEN 1 ELSE 0 END)      AS qa_failed,
                    SUM(CASE WHEN e.event_type = 'merge_start'  THEN 1 ELSE 0 END)      AS merge_runs,
                    SUM(CASE WHEN e.event_type = 'merge_failed' THEN 1 ELSE 0 END)      AS merge_failed
                FROM events e
                JOIN rework_issues ri ON ri.project = e.project AND ri.issue_number = e.issue_number
                GROUP BY e.project, e.issue_number
                ORDER BY (SUM(CASE WHEN e.event_type LIKE '%_start' THEN 1 ELSE 0 END)) DESC
                LIMIT ? OFFSET ?
            )
            SELECT
                a.*,
                (
                    SELECT COUNT(*)
                    FROM verdicts v
                    WHERE v.project = a.project
                      AND v.created_at BETWEEN a.first_event AND a.last_event
                ) AS verdict_count,
                (
                    SELECT COALESCE(SUM(v.points), 0)
                    FROM verdicts v
                    WHERE v.project = a.project
                      AND v.created_at BETWEEN a.first_event AND a.last_event
                ) AS total_points
            FROM agg a
            """,
            params_day,
        ).fetchall()
    else:
        rows = conn.execute(
            """
            WITH agg AS (
                SELECT
                    project,
                    issue_number,
                    MIN(created_at)                                                    AS first_event,
                    MAX(created_at)                                                    AS last_event,
                    SUM(CASE WHEN event_type LIKE '%_start'   THEN 1 ELSE 0 END)      AS actual_runs,
                    SUM(CASE WHEN event_type = 'po_start'     THEN 1 ELSE 0 END)      AS po_runs,
                    SUM(CASE WHEN event_type = 'po_failed'    THEN 1 ELSE 0 END)      AS po_failed,
                    SUM(CASE WHEN event_type = 'dev_start'    THEN 1 ELSE 0 END)      AS dev_runs,
                    SUM(CASE WHEN event_type = 'dev_failed'   THEN 1 ELSE 0 END)      AS dev_failed,
                    SUM(CASE WHEN event_type = 'review_start' THEN 1 ELSE 0 END)      AS review_runs,
                    SUM(CASE WHEN event_type = 'review_failed' THEN 1 ELSE 0 END)     AS review_failed,
                    SUM(CASE WHEN event_type = 'qa_start'     THEN 1 ELSE 0 END)      AS qa_runs,
                    SUM(CASE WHEN event_type = 'qa_failed'    THEN 1 ELSE 0 END)      AS qa_failed,
                    SUM(CASE WHEN event_type = 'merge_start'  THEN 1 ELSE 0 END)      AS merge_runs,
                    SUM(CASE WHEN event_type = 'merge_failed' THEN 1 ELSE 0 END)      AS merge_failed
                FROM events
                WHERE issue_number IS NOT NULL
                  AND created_at >= ?
                  AND (? IS NULL OR project = ?)
                GROUP BY project, issue_number
                HAVING actual_runs > 0
                ORDER BY actual_runs DESC
                LIMIT ? OFFSET ?
            )
            SELECT
                a.*,
                (
                    SELECT COUNT(*)
                    FROM verdicts v
                    WHERE v.project = a.project
                      AND v.created_at BETWEEN a.first_event AND a.last_event
                ) AS verdict_count,
                (
                    SELECT COALESCE(SUM(v.points), 0)
                    FROM verdicts v
                    WHERE v.project = a.project
                      AND v.created_at BETWEEN a.first_event AND a.last_event
                ) AS total_points
            FROM agg a
            """,
            (since_iso, project_param, project_param, limit, offset),
        ).fetchall()

    now_ts = datetime.now(timezone.utc).timestamp()
    result = []
    for raw in rows:
        raw_dict = dict(raw)
        project_slug = raw_dict["project"]
        issue_num = raw_dict["issue_number"]
        meta = _fetch_gh_meta(project_slug, issue_num)
        result.append(_build_row(raw_dict, meta, now_ts))

    result.sort(key=lambda r: (-r["rework_factor"], -r["actual_runs"]))
    return result


def _median(values: list[float]) -> Optional[float]:
    """Compute median of a list of floats. Returns None for empty list."""
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return round((s[mid - 1] + s[mid]) / 2, 4)
    return round(s[mid], 4)


def _linear_trend_slope(values: list[float]) -> float:
    """Return slope from simple linear regression over evenly-spaced points."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    num = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


@router.get("/api/cost/trend")
def get_cost_trend(
    days: int = 30,
    project: Optional[str] = None,
    priority: Optional[str] = None,
    conn: sqlite3.Connection = Depends(db_dep),
) -> dict[str, Any]:
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    since_iso = since_dt.isoformat()

    # Fetch all events in the window to compute per-issue rework factors per day
    rows = conn.execute(
        """
        SELECT
            date(created_at)   AS day,
            project,
            issue_number,
            SUM(CASE WHEN event_type LIKE '%_start' THEN 1 ELSE 0 END) AS actual_runs
        FROM events
        WHERE issue_number IS NOT NULL
          AND created_at >= ?
          AND (? IS NULL OR project = ?)
        GROUP BY day, project, issue_number
        HAVING actual_runs > 0
        """,
        (since_iso, project, project),
    ).fetchall()

    # Build a map of day -> list of rework_factors
    # rework_factor per (day, issue) = actual_runs_that_day / 5  (simplified happy path = 5, no child info here)
    # We use the same formula as _build_row but without child_count (would require GH API per day per issue)
    day_factors: dict[str, list[float]] = {}
    for row in rows:
        day: str = row["day"]
        actual: int = row["actual_runs"] or 0
        if actual == 0:
            continue
        # simple rework factor without child lookup (consistent for trend)
        rf = round(actual / 5, 4)
        day_factors.setdefault(day, []).append(rf)

    # Apply priority filter if given — we need to know which (project, issue_number) have that priority
    # We fetch all issues in window and then filter by priority via GH meta
    if priority:
        # collect all unique (project, issue_number) in the window
        meta_rows = conn.execute(
            """
            SELECT DISTINCT project, issue_number
            FROM events
            WHERE issue_number IS NOT NULL
              AND created_at >= ?
              AND (? IS NULL OR project = ?)
            """,
            (since_iso, project, project),
        ).fetchall()
        allowed: set[tuple[str, int]] = set()
        for mr in meta_rows:
            meta = _fetch_gh_meta(mr["project"], mr["issue_number"])
            if meta.get("priority") == priority:
                allowed.add((mr["project"], mr["issue_number"]))

        # rebuild day_factors filtered to allowed issues
        day_factors = {}
        for row in rows:
            key = (row["project"], row["issue_number"])
            if key not in allowed:
                continue
            day: str = row["day"]
            actual = row["actual_runs"] or 0
            if actual == 0:
                continue
            rf = round(actual / 5, 4)
            day_factors.setdefault(day, []).append(rf)

    # Build sorted list of days in the window
    today_dt = datetime.now(timezone.utc).date()
    all_days = [(today_dt - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    buckets: list[dict[str, Any]] = []
    for d in all_days:
        factors = day_factors.get(d, [])
        med = _median(factors)
        buckets.append({
            "date": d,
            "median_rework_factor": med,
            "issue_count": len(factors),
        })

    # today's stats
    today_factors = day_factors.get(today_dt.isoformat(), [])
    today_median = _median(today_factors)
    today_count = len(today_factors)

    # comparison helpers
    def _median_for_day(offset_days: int) -> Optional[float]:
        d = (today_dt - timedelta(days=offset_days)).isoformat()
        return _median(day_factors.get(d, []))

    def _delta(ref: Optional[float]) -> Optional[float]:
        if today_median is None or ref is None:
            return None
        return round(today_median - ref, 4)

    vs_7d = _delta(_median_for_day(7))
    vs_30d = _delta(_median_for_day(30))

    # trend from linear regression on last 14 buckets that have data
    recent_medians = [b["median_rework_factor"] for b in buckets[-14:] if b["median_rework_factor"] is not None]
    if len(recent_medians) >= 3:
        slope = _linear_trend_slope(recent_medians)
        if slope < -0.01:
            trend = "improving"
        elif slope > 0.01:
            trend = "degrading"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return {
        "window_days": days,
        "today": {
            "median_rework_factor": today_median,
            "issue_count": today_count,
        },
        "vs_7d": vs_7d,
        "vs_30d": vs_30d,
        "trend": trend,
        "buckets": buckets,
    }


@router.get("/api/cost/timeseries")
def get_cost_timeseries(
    days: int = 30,
    project: Optional[str] = None,
    priority: Optional[str] = None,
    conn: sqlite3.Connection = Depends(db_dep),
) -> dict[str, Any]:
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    since_iso = since_dt.isoformat()

    rework_types_ph = ",".join("?" * len(_REWORK_EVENT_TYPES))

    # Single query: per-day per-issue rework event counts by stage
    issue_rows = conn.execute(
        f"""
        SELECT
            date(created_at)                                                          AS day,
            project,
            issue_number,
            SUM(CASE WHEN event_type = 'po_failed'                         THEN 1 ELSE 0 END) AS po_failed,
            SUM(CASE WHEN event_type IN ('dev_failed', 'dev_rework')        THEN 1 ELSE 0 END) AS dev_rework,
            SUM(CASE WHEN event_type = 'qa_failed'                         THEN 1 ELSE 0 END) AS qa_fail,
            SUM(CASE WHEN event_type = 'review_failed'                     THEN 1 ELSE 0 END) AS review_reject,
            COUNT(*)                                                                AS rework_events
        FROM events
        WHERE issue_number IS NOT NULL
          AND created_at >= ?
          AND (? IS NULL OR project = ?)
          AND event_type IN ({rework_types_ph})
        GROUP BY day, project, issue_number
        ORDER BY day, rework_events DESC
        """,
        (since_iso, project, project, *_REWORK_EVENT_TYPES),
    ).fetchall()

    # Apply priority filter if requested
    if priority:
        unique_issues = {(r["project"], r["issue_number"]) for r in issue_rows}
        allowed: set[tuple[str, int]] = set()
        for proj, iss in unique_issues:
            meta = _fetch_gh_meta(proj, iss)
            if meta.get("priority") == priority:
                allowed.add((proj, iss))
        issue_rows = [r for r in issue_rows if (r["project"], r["issue_number"]) in allowed]

    # Aggregate per-day totals and build top_issues
    day_stage: dict[str, dict[str, int]] = {}
    day_issues: dict[str, list[dict[str, Any]]] = {}
    for row in issue_rows:
        d: str = row["day"]
        if d not in day_stage:
            day_stage[d] = {"po_failed": 0, "dev_rework": 0, "qa_fail": 0, "review_reject": 0}
            day_issues[d] = []
        day_stage[d]["po_failed"]     += row["po_failed"]
        day_stage[d]["dev_rework"]    += row["dev_rework"]
        day_stage[d]["qa_fail"]       += row["qa_fail"]
        day_stage[d]["review_reject"] += row["review_reject"]
        day_issues[d].append({
            "project": row["project"],
            "issue_number": row["issue_number"],
            "rework_events": row["rework_events"],
        })

    today_dt = datetime.now(timezone.utc).date()
    all_days = [(today_dt - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    buckets: list[dict[str, Any]] = []
    for d in all_days:
        stage = day_stage.get(d, {"po_failed": 0, "dev_rework": 0, "qa_fail": 0, "review_reject": 0})
        total = stage["po_failed"] + stage["dev_rework"] + stage["qa_fail"] + stage["review_reject"]
        # issues already sorted by rework_events DESC from SQL
        top = day_issues.get(d, [])[:3]
        buckets.append({
            "date": d,
            "total_rework_events": total,
            "by_stage": stage,
            "top_issues": top,
        })

    return {"window_days": days, "buckets": buckets}
