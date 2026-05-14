import re
import time


def test_get_root_returns_dashboard_html(isolated_client):
    response = isolated_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Loop Monitor" in response.text


def test_health_core_version_counts(isolated_client):
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.1.0",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.1.0",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.2.0",
    })
    resp = isolated_client.get("/api/health")
    assert resp.status_code == 200
    counts = resp.json()["core_version_counts"]
    assert counts["0.1.0"] == 2
    assert counts["0.2.0"] == 1


def test_loops_empty_db(isolated_client):
    resp = isolated_client.get("/api/loops")
    assert resp.status_code == 200
    assert resp.json() == []


def test_loops_with_data(isolated_client):
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "loop_id": "loop-1", "core_version": "0.1.0",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "loop_id": "loop-1", "core_version": "0.2.0",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.1.0",
    })
    time.sleep(0.1)  # background tasks

    resp = isolated_client.get("/api/loops")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    unknown = next(r for r in data if r["loop_id"] == "(unknown)")
    assert unknown["event_count"] == 1
    assert unknown["core_versions"] == ["0.1.0"]

    loop1 = next(r for r in data if r["loop_id"] == "loop-1")
    assert loop1["event_count"] == 2
    assert sorted(loop1["core_versions"]) == ["0.1.0", "0.2.0"]
    assert "last_seen" in loop1


def test_health_loop_ids_field(isolated_client):
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "loop_id": "loop-a",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
    })
    time.sleep(0.1)  # background tasks

    resp = isolated_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "loop_ids" in data
    assert "(unknown)" in data["loop_ids"]
    assert "loop-a" in data["loop_ids"]


def test_health_git_sha_field(isolated_client):
    resp = isolated_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "git_sha" in data
    sha = data["git_sha"]
    assert sha == "unknown" or re.match(r"^[0-9a-f]{7}$", sha)


def test_health_latest_main_sha_field(isolated_client):
    resp = isolated_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "latest_main_sha" in data
    sha = data["latest_main_sha"]
    # Either "unknown" (network unavailable in test env) or a valid short sha
    assert sha == "unknown" or re.match(r"^[0-9a-f]{7}$", sha)


def test_health_latest_main_sha_cached(isolated_client, monkeypatch):
    import server.routes.health as h
    call_count = 0
    original = h._latest_main_sha

    def counting_latest():
        nonlocal call_count
        call_count += 1
        return "abc1234"

    monkeypatch.setattr(h, "_latest_main_sha", counting_latest)
    # Reset cache so our mock is used
    h._LATEST_SHA_CACHE = None

    resp1 = isolated_client.get("/api/health")
    resp2 = isolated_client.get("/api/health")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Both calls should return "abc1234" from our mock
    assert resp1.json()["latest_main_sha"] == "abc1234"
    assert resp2.json()["latest_main_sha"] == "abc1234"

    monkeypatch.setattr(h, "_latest_main_sha", original)


def test_health_loop_ids_empty_db(isolated_client):
    resp = isolated_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "loop_ids" in data
    assert data["loop_ids"] == []
