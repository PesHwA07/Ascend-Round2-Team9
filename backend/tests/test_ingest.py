import pytest

def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "aurabrief-backend"
    assert data["database"] == "connected"

def test_ingest_three_streams(client):
    """Test ingestion from the 3 official streams defined in API_SCHEMA.md."""
    sample_events = [
        {
            "event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "source": "infra-monitor",
            "severity": "critical",
            "service": "payment-api",
            "region": "us-east",
            "title": "CPU usage at 95% on payment-api node",
            "details": {
                "metric_name": "cpu_utilization_percent",
                "metric_value": 95.2,
                "threshold": 80.0,
                "duration_seconds": 300
            },
            "tags": ["infrastructure", "performance", "cpu"]
        },
        {
            "event_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "source": "app-errors",
            "severity": "critical",
            "service": "payment-api",
            "region": "us-east",
            "title": "HTTP 5xx spike: 23% error rate on /payments/process",
            "details": {
                "error_type": "http_5xx_spike",
                "error_count": 347,
                "time_window_seconds": 300,
                "endpoint": "/api/v1/payments/process",
                "error_rate_percent": 23.4,
                "sample_error": "java.sql.SQLTransientConnectionException: Connection pool exhausted"
            },
            "tags": ["application", "errors", "http-5xx"]
        },
        {
            "event_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
            "source": "deploy-events",
            "severity": "warning",
            "service": "gateway",
            "region": "eu-west",
            "title": "Deploy failed: gateway v2.4.0 in eu-west",
            "details": {
                "deploy_type": "deploy_failed",
                "version_from": "v2.3.1",
                "version_to": "v2.4.0",
                "deployed_by": "ci-bot",
                "commit_sha": "a1b2c3d",
                "failure_reason": "Health check timeout after 120s"
            },
            "tags": ["deployment", "failure", "ci-cd"]
        }
    ]

    response = client.post(
        "/api/events/ingest",
        json={"events": sample_events, "trigger_triage": True}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["received_count"] == 3
    assert len(data["event_ids"]) == 3
    assert data["event_ids"][0] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

def test_ingest_schema_aliases(client):
    """Verify alias support: stream_source/source, raw_payload/details, id/event_id."""
    alias_payload = {
        "events": [
            {
                "id": "test-alias-uuid-1",
                "stream_source": "infra-monitor",
                "severity": "high",
                "service": "auth-gateway",
                "region": "us-west",
                "title": "Authentication Latency Spike",
                "raw_payload": {"latency_p99_ms": 3200}
            }
        ],
        "trigger_triage": False
    }
    response = client.post("/api/events/ingest", json=alias_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["received_count"] == 1
    assert data["event_ids"][0] == "test-alias-uuid-1"

def test_invalid_event_validation(client):
    """Verify invalid payload handling (422 Unprocessable Entity)."""
    invalid_payload = {
        "events": [
            {
                "severity": "critical"
                # Missing source, service, title
            }
        ]
    }
    response = client.post("/api/events/ingest", json=invalid_payload)
    assert response.status_code == 422
