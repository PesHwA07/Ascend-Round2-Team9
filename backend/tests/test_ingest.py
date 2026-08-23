import pytest

def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

def test_ingest_three_streams(client):
    sample_events = [
        {
            "stream_source": "infra_apm",
            "event_type": "high_cpu",
            "severity": "critical",
            "service": "payment-api",
            "environment": "production",
            "region": "us-east-1",
            "title": "CPU utilization exceeded 95%",
            "description": "Instance pool i-0192 under heavy load",
            "raw_payload": {"cpu_percent": 98.2, "instances": 4}
        },
        {
            "stream_source": "auth_security",
            "event_type": "failed_login_burst",
            "severity": "high",
            "service": "auth-gateway",
            "environment": "production",
            "region": "eu-west-1",
            "title": "Abnormal credential stuffing detected",
            "description": "500 failed logins in 60 seconds from IP subnet",
            "raw_payload": {"failed_attempts": 500, "unique_users": 42}
        },
        {
            "stream_source": "app_business",
            "event_type": "checkout_latency_spike",
            "severity": "medium",
            "service": "cart-checkout",
            "environment": "production",
            "region": "global",
            "title": "P99 latency above SLA",
            "description": "Checkout completion taking > 4.5 seconds",
            "raw_payload": {"latency_p99_ms": 4600, "orders_affected": 120}
        }
    ]

    response = client.post(
        "/api/events/ingest",
        json={"events": sample_events, "trigger_triage": True}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ingested_count"] == 3
    assert len(data["events"]) == 3
    assert data["batch_id"] is not None

def test_triage_current_after_ingest(client):
    # Ingest test event
    client.post(
        "/api/events/ingest",
        json={
            "events": [
                {
                    "stream_source": "infra_apm",
                    "event_type": "database_deadlock",
                    "severity": "critical",
                    "service": "order-db",
                    "environment": "production",
                    "region": "us-east-1",
                    "title": "Deadlock detected in order transaction pool",
                    "description": "Transactions rolling back",
                    "raw_payload": {"deadlock_count": 14}
                }
            ],
            "trigger_triage": True
        }
    )

    response = client.get("/api/triage/current")
    assert response.status_code == 200
    data = response.json()
    assert data["total_events_evaluated"] >= 1
    assert len(data["items"]) >= 1
    top_item = data["items"][0]
    assert top_item["rank"] == 1
    assert top_item["event"]["service"] == "order-db"
    assert "explanation" in top_item
    assert "suggested_action" in top_item
