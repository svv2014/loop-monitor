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

# Batch cache: project -> {issue_number: meta_dict}
_gh_batch_cache: dict[str, dict[int, dict]] = {}
_GH_BATCH_TTL = 60

_PRIORITY_LABELS = {"p0-critical", "p1-high", "p2-medium", "p3-low"}
_ROLES = ["po", "dev", "review", "qa", "merge"]
_CHILD_RE = re.compile(r"(?:closes|depends\s+on)\s+#(\d+)", re.IGNORECASE)


def _fetch_gh_batch(project: str) -> dict[int, dict]:
    """Fetch ALL open issues for a project in one gh api call."""
    now = datetime.now(timezone.utc).timestamp()
    if project in _gh_batch_cache:
        expiry, data = _gh_batch_cache[project]
        if now < expiry:
            return data

    repo = PROJECTS.get(project)
    empty: dict[int, dict] = {}
    if not repo:
        _gh_batch_cache[project] = (now + _GH_BATCH_TTL, empty)
        return empty

    default_meta = {"title": "", "state": "unknown", "priority": None, "body": "", "merged": False}
    result_map: dict[int, dict] = {}

    try:
        # Single API call to list all open issues for the repo
        result = subprocess.run(
            [
                "gh", "api",
                f"repos/{repo}/issues?state=all&per_page=100",
                "--jq", ".[] | {number, title, state, body, labels: [.labels[].name], pull_request}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            _gh_batch_cache[project] = (now + _GH_BATCH_TTL, empty)
            return empty

        # Parse line-by-line JSON output (--jq with .[] outputs one JSON per line)
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            num = raw.get("number")
            if num is None:
                continue
            labels: list[str] = raw.get("labels") or []
            priority: Optional[str] = next((lbl for lbl in labels if lbl in _PRIORITY_LABELS), None)
            pr_field = raw.get("pull_request") or {}
            merged = bool(pr_field.get("merged_at"))
            result_map[num] = {
                "title": raw.get("title") or "",
                "state": raw.get("state") or "unknown",
                "priority": priority,
                "body": raw.get("body") or "",
                "merged": merged,
            }
    except Exception:
        _gh_batch_cache[project] = (now + _GH_BATCH_TTL, empty)
        return empty

    _gh_batch_cache[project] = (now + _GH_BATCH_TTL, result_map)
    return result_map


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


@router.get("/api/issues/cost")
def get_issues_cost(
    project: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    conn: sqlite3.Connection = Depends(db_dep),
) -> list:
    if since is None:
        since_dt = datetime.now(timezone.utc) - timedelta(days=30)
        since_iso = since_dt.isoformat()
    else:
        since_iso = since

    project_param: Optional[str] = project

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

    # Batch-fetch GH metadata per project instead of per issue
    projects_in_rows = {dict(r)["project"] for r in rows}
    batch_meta: dict[str, dict[int, dict]] = {}
    for proj in projects_in_rows:
        batch_meta[proj] = _fetch_gh_batch(proj)

    default_meta = {"title": "", "state": "unknown", "priority": None, "body": "", "merged": False}
    result = []
    for raw in rows:
        raw_dict = dict(raw)
        project_slug = raw_dict["project"]
        issue_num = raw_dict["issue_number"]
        meta = batch_meta.get(project_slug, {}).get(issue_num, default_meta)
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

    # Batch-fetch GH metadata for priority filtering
    default_meta = {"title": "", "state": "unknown", "priority": None, "body": "", "merged": False}
    if priority:
        projects_in_rows = {r["project"] for r in rows}
        batch_meta: dict[str, dict[int, dict]] = {}
        for proj in projects_in_rows:
            batch_meta[proj] = _fetch_gh_batch(proj)

        allowed: set[tuple[str, int]] = set()
        for row in rows:
            key = (row["project"], row["issue_number"])
            meta = batch_meta.get(row["project"], {}).get(row["issue_number"], default_meta)
            if meta.get("priority") == priority:
                allowed.add(key)

        day_factors: dict[str, list[float]] = {}
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
    else:
        day_factors: dict[str, list[float]] = {}
        for row in rows:
            day: str = row["day"]
            actual: int = row["actual_runs"] or 0
            if actual == 0:
                continue
            rf = round(actual / 5, 4)
            day_factors.setdefault(day, []).append(rf)

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

    today_factors = day_factors.get(today_dt.isoformat(), [])
    today_median = _median(today_factors)
    today_count = len(today_factors)

    def _median_for_day(offset_days: int) -> Optional[float]:
        d = (today_dt - timedelta(days=offset_days)).isoformat()
        return _median(day_factors.get(d, []))

    def _delta(ref: Optional[float]) -> Optional[float]:
        if today_median is None or ref is None:
            return None
        return round(today_median - ref, 4)

    vs_7d = _delta(_median_for_day(7))
    vs_30d = _delta(_median_for_day(30))

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
