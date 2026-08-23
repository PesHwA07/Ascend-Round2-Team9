import pytest
import time

def test_ranking_priority_ordering(client):
    # Ingest 3 events of distinct severities
    events = [
        {
            "stream_source": "infra_apm",
            "event_type": "minor_log_warning",
            "severity": "low",
            "service": "logger-service",
            "title": "Disk buffer 40% full",
            "raw_payload": {}
        },
        {
            "stream_source": "infra_apm",
            "event_type": "api_outage",
            "severity": "critical",
            "service": "core-gateway",
            "title": "API Gateway 502 Bad Gateway Outage",
            "raw_payload": {"error_rate_pct": 89.5, "affected_users": 15000}
        },
        {
            "stream_source": "app_business",
            "event_type": "minor_latency",
            "severity": "medium",
            "service": "notification-service",
            "title": "Email delivery delayed by 3s",
            "raw_payload": {}
        }
    ]

    client.post("/api/events/ingest", json={"events": events, "trigger_triage": True})

    response = client.get("/api/triage/current")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 3

    # Rank 1 must be the critical API outage
    assert items[0]["rank"] == 1
    assert items[0]["event"]["service"] == "core-gateway"
    assert items[0]["priority_score"] > items[1]["priority_score"]
    assert items[1]["priority_score"] > items[2]["priority_score"]

def test_triage_under_5_seconds_sla(client):
    """Verify Non-Functional Requirement: End-to-end triage path completes within 5 seconds."""
    batch = []
    for i in range(50):
        batch.append({
            "stream_source": "infra_apm" if i % 3 == 0 else ("auth_security" if i % 3 == 1 else "app_business"),
            "event_type": f"event_type_{i % 5}",
            "severity": "critical" if i % 4 == 0 else "high",
            "service": f"service-{i % 6}",
            "title": f"Simulated Event #{i}",
            "raw_payload": {"metric": i * 1.5, "latency_p99_ms": 1200 + i * 10}
        })

    start_time = time.perf_counter()
    response = client.post("/api/events/ingest", json={"events": batch, "trigger_triage": True})
    elapsed = time.perf_counter() - start_time

    assert response.status_code == 201
    assert elapsed < 5.0, f"Triage SLA violated: took {elapsed:.2f}s (expected < 5.0s)"

    # Check triage response time recorded
    current_resp = client.get("/api/triage/current")
    assert current_resp.status_code == 200
    assert current_resp.json()["execution_time_ms"] < 5000.0

def test_triage_history_and_replay(client):
    # Ingest event 1
    client.post("/api/events/ingest", json={
        "events": [{
            "stream_source": "infra_apm",
            "event_type": "mem_leak",
            "severity": "high",
            "service": "cache-node",
            "title": "Cache memory 88%"
        }],
        "trigger_triage": True
    })

    # Ingest event 2
    client.post("/api/events/ingest", json={
        "events": [{
            "stream_source": "auth_security",
            "event_type": "unauthorized_admin",
            "severity": "critical",
            "service": "admin-panel",
            "title": "Unauthorized admin login attempt"
        }],
        "trigger_triage": True
    })

    history_resp = client.get("/api/triage/history")
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["total_snapshots"] >= 2

    # Replay specific snapshot
    first_snapshot_id = history_data["snapshots"][-1]["id"]
    replay_resp = client.get(f"/api/triage/replay/{first_snapshot_id}")
    assert replay_resp.status_code == 200
    assert replay_resp.json()["snapshot_id"] == first_snapshot_id
