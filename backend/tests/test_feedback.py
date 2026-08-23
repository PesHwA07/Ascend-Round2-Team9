import pytest

def test_get_weights_5_signals(client):
    response = client.get("/api/weights")
    assert response.status_code == 200
    data = response.json()
    weights = data["weights"]
    assert "severity" in weights
    assert "frequency" in weights
    assert "recency" in weights
    assert "anomaly" in weights
    assert "business_impact" in weights

def test_submit_feedback_returns_reranked_events(client):
    # Ingest baseline event
    client.post("/api/events/ingest", json={
        "events": [{
            "source": "infra-monitor",
            "severity": "critical",
            "service": "payment-api",
            "title": "Payment CPU high",
            "details": {}
        }],
        "trigger_triage": True
    })

    feedback_payload = {
        "weights": {
            "severity": 0.40,
            "frequency": 0.15,
            "recency": 0.15,
            "anomaly": 0.15,
            "business_impact": 0.15
        },
        "operator_notes": "Boost severity during active triage window",
        "re_triage_now": True
    }

    response = client.post("/api/feedback", json=feedback_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "weights_updated"
    assert data["weights"]["severity"] == 0.40
    assert data["ranked_events"] is not None
    assert len(data["ranked_events"]) >= 1

def test_audit_log_format_and_filtering(client):
    client.post("/api/events/ingest", json={
        "events": [{
            "source": "deploy-events",
            "severity": "info",
            "service": "worker-service",
            "title": "Deploy started for worker",
            "details": {}
        }],
        "trigger_triage": True
    })

    # Fetch audit logs
    audit_resp = client.get("/api/audit-log?limit=20")
    assert audit_resp.status_code == 200
    data = audit_resp.json()
    assert data["total"] >= 1
    
    first_log = data["logs"][0]
    assert "step" in first_log
    assert "level" in first_log
    assert "message" in first_log
    assert "duration_ms" in first_log
    
    # Test level filter
    info_resp = client.get("/api/audit-log?level=info")
    assert info_resp.status_code == 200
    assert info_resp.json()["total"] >= 1
