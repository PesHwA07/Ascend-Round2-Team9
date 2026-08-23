import pytest
import time

def test_ranking_5_signals_and_breakdown(client):
    """Test that ranking computes all 5 signals and populates score_breakdown."""
    events = [
        {
            "event_id": "evt-low-1",
            "source": "infra-monitor",
            "severity": "info",
            "service": "logger-service",
            "region": "us-east",
            "title": "Minor log flush note",
            "details": {}
        },
        {
            "event_id": "evt-crit-1",
            "source": "app-errors",
            "severity": "critical",
            "service": "payment-api",
            "region": "us-east",
            "title": "Payment gateway outage 5xx spike",
            "details": {"error_rate_percent": 35.0, "affected_orders": 1200}
        },
        {
            "event_id": "evt-warn-1",
            "source": "deploy-events",
            "severity": "warning",
            "service": "cart-checkout",
            "region": "eu-west",
            "title": "Deploy rollback on cart",
            "details": {"deploy_type": "rollback_triggered"}
        }
    ]

    client.post("/api/events/ingest", json={"events": events, "trigger_triage": True})

    response = client.get("/api/triage/current")
    assert response.status_code == 200
    data = response.json()
    
    assert "triage_id" in data
    assert "ranked_events" in data
    ranked = data["ranked_events"]
    assert len(ranked) == 3

    # Rank 1 must be critical payment-api
    top = ranked[0]
    assert top["rank"] == 1
    assert top["service"] == "payment-api"
    assert top["score"] > ranked[1]["score"]
    assert top["explanation_type"] in ["ai", "template"]
    assert "explanation" in top
    assert "suggested_action" in top
    
    # Verify 5-signal breakdown
    bd = top["score_breakdown"]
    assert "severity" in bd
    assert "frequency" in bd
    assert "recency" in bd
    assert "anomaly" in bd
    assert "business_impact" in bd

def test_triage_under_5_seconds_sla(client):
    """
    Verify Non-Functional Requirement:
    Batch ingestion of 50 multi-stream events with ranking and explanations completes in < 1 second (< 5s SLA).
    """
    batch = []
    sources = ["infra-monitor", "app-errors", "deploy-events"]
    severities = ["critical", "warning", "info"]
    services = ["payment-api", "gateway", "auth-service", "cart-checkout", "worker-node"]
    
    for i in range(50):
        batch.append({
            "event_id": f"sla-test-evt-{i}",
            "source": sources[i % 3],
            "severity": severities[i % 3],
            "service": services[i % 5],
            "region": "us-east" if i % 2 == 0 else "eu-west",
            "title": f"Simulated Event #{i} on {services[i % 5]}",
            "details": {
                "error_rate_percent": (i * 1.5) % 40,
                "metric_value": 70 + (i % 30),
                "threshold": 80
            },
            "tags": ["sla-test"]
        })

    start_time = time.perf_counter()
    response = client.post("/api/events/ingest", json={"events": batch, "trigger_triage": True})
    elapsed = time.perf_counter() - start_time

    assert response.status_code == 200
    assert elapsed < 1.0, f"Benchmark target missed: took {elapsed:.3f}s (expected < 1.0s)"
    assert elapsed < 5.0, f"SLA violated: took {elapsed:.3f}s (expected < 5.0s)"

    # Verify triage execution time
    triage_resp = client.get("/api/triage/current")
    assert triage_resp.status_code == 200
    triage_data = triage_resp.json()
    assert triage_data["execution_time_ms"] < 5000.0

def test_triage_history_and_replay_by_id(client):
    """Verify GET /api/triage/history and GET /api/triage/history/{triage_id}."""
    # Ingest event 1
    client.post("/api/events/ingest", json={
        "events": [{
            "source": "infra-monitor",
            "severity": "critical",
            "service": "redis-cluster",
            "title": "Redis cluster node failure",
            "details": {}
        }],
        "trigger_triage": True
    })

    # Ingest event 2
    client.post("/api/events/ingest", json={
        "events": [{
            "source": "deploy-events",
            "severity": "warning",
            "service": "api-gateway",
            "title": "Deploy timeout on api-gateway",
            "details": {}
        }],
        "trigger_triage": True
    })

    hist_resp = client.get("/api/triage/history")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert len(hist_data["history"]) >= 2

    # Test replay by triage_id
    first_id = hist_data["history"][-1]["triage_id"]
    replay_resp = client.get(f"/api/triage/history/{first_id}")
    assert replay_resp.status_code == 200
    replay_data = replay_resp.json()
    assert replay_data["triage_id"] == first_id
    assert len(replay_data["ranked_events"]) >= 1
