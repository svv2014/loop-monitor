"""QA-driven tests for PR #297 — _github_url helper and github_url in feed/history."""
import sqlite3
from unittest.mock import patch

import server
import server.db
from server.routes.feed import _github_url


# --- Unit tests for _github_url helper ---

def test_github_url_issue_number():
    with patch("server.routes.feed.PROJECTS", {"myproj": "owner/repo"}):
        result = _github_url("myproj", issue_number=42, pr_number=None)
    assert result == "https://github.com/owner/repo/issues/42"


def test_github_url_pr_number():
    with patch("server.routes.feed.PROJECTS", {"myproj": "owner/repo"}):
        result = _github_url("myproj", issue_number=None, pr_number=7)
    assert result == "https://github.com/owner/repo/pull/7"


def test_github_url_issue_takes_priority_over_pr():
    with patch("server.routes.feed.PROJECTS", {"myproj": "owner/repo"}):
        result = _github_url("myproj", issue_number=1, pr_number=2)
    assert result == "https://github.com/owner/repo/issues/1"


def test_github_url_no_numbers_returns_none():
    with patch("server.routes.feed.PROJECTS", {"myproj": "owner/repo"}):
        result = _github_url("myproj", issue_number=None, pr_number=None)
    assert result is None


def test_github_url_unknown_project_returns_none():
    with patch("server.routes.feed.PROJECTS", {}):
        result = _github_url("unknown-proj", issue_number=5, pr_number=None)
    assert result is None


# --- Integration tests: github_url present on feed and history endpoints ---

def test_feed_includes_github_url_field(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-gurl", role="dev", event_type="dev_done"
    ))
    resp = isolated_client.get("/api/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    item = next((i for i in data if i["project"] == "proj-gurl"), None)
    assert item is not None
    assert "github_url" in item


def test_feed_github_url_is_none_when_no_project_config(isolated_client):
    """Events for projects not in PROJECTS config get github_url=null."""
    with patch("server.routes.feed.PROJECTS", {}):
        server._insert_event(server.ReportPayload(
            project="unregistered-proj", role="dev", event_type="dev_done"
        ))
        resp = isolated_client.get("/api/feed")
    assert resp.status_code == 200
    data = resp.json()
    item = next((i for i in data if i["project"] == "unregistered-proj"), None)
    assert item is not None
    assert item["github_url"] is None


def test_feed_github_url_populated_when_issue_number_and_project_known(isolated_client, monkeypatch):
    monkeypatch.setattr("server.routes.feed.PROJECTS", {"proj-linked": "myorg/myrepo"})
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, created_at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        ("proj-linked", "dev", "dev_done", 99),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/feed")
    assert resp.status_code == 200
    item = next((i for i in resp.json() if i["project"] == "proj-linked"), None)
    assert item is not None
    assert item["github_url"] == "https://github.com/myorg/myrepo/issues/99"


def test_history_includes_github_url_field(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, created_at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        ("proj-hist-url", "dev", "dev_done", None),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/history")
    assert resp.status_code == 200
    data = resp.json()
    assert all("github_url" in i for i in data)
