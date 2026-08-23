import pytest

def test_get_weights(client):
    response = client.get("/api/weights")
    assert response.status_code == 200
    data = response.json()
    assert "severity_weight" in data
    assert "blast_radius_weight" in data
    assert "anomaly_weight" in data
    assert "recurrence_weight" in data

def test_submit_feedback_adjusts_weights(client):
    feedback_payload = {
        "severity_weight": 0.50,
        "blast_radius_weight": 0.30,
        "anomaly_weight": 0.10,
        "recurrence_weight": 0.10,
        "operator_notes": "Prioritize severity and blast radius during active maintenance window",
        "re_triage_now": True
    }

    response = client.post("/api/feedback", json=feedback_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["weights"]["severity_weight"] == 0.50

    # Verify updated weights on subsequent GET
    get_resp = client.get("/api/weights")
    assert get_resp.status_code == 200
    assert get_resp.json()["severity_weight"] == 0.50

def test_audit_log_records_actions(client):
    # Perform actions
    client.post("/api/events/ingest", json={
        "events": [{
            "stream_source": "infra_apm",
            "event_type": "pod_crash",
            "severity": "high",
            "service": "worker-1",
            "title": "Worker pod crashed"
        }],
        "trigger_triage": True
    })

    client.post("/api/feedback", json={
        "severity_weight": 0.40,
        "operator_notes": "Test weight tweak",
        "re_triage_now": False
    })

    audit_resp = client.get("/api/audit-log")
    assert audit_resp.status_code == 200
    data = audit_resp.json()
    assert data["total"] >= 2
    actions = [entry["action"] for entry in data["logs"]]
    assert "INGEST_EVENTS" in actions
    assert "UPDATE_WEIGHTS" in actions
