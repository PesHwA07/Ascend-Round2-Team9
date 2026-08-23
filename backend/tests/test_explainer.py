"""Gen-AI explainer tests.

No live Ollama server required: every HTTP interaction is mocked with
httpx.MockTransport. Ranking data is consumed verbatim and asserted immutable.

Fixtures mirror the ACTUAL backend contracts (feature/backend-integration):
    rank_events() item -> {
        "event": Event,
        "rank": int,
        "score": float (0.0-1.0),          # aliased as priority_score
        "score_breakdown": {                # weighted contributions
            "severity", "frequency", "recency", "anomaly", "business_impact"
        },
    }
    Event -> source/details/tags/timestamp/severity/service/environment/region

Agreed Gen-AI contract:
    await generate_explanation(event, ranking_data) -> {
        "summary": str,
        "why_prioritized": str,
        "recommended_action": str,
        "provider": "ollama" | "fallback",
    }
"""

import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from backend.app.services import explainer


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_explainer_state():
    explainer.reset_cooldown()
    yield
    explainer.reset_cooldown()


def make_event(**overrides):
    """Actual Event schema: source / details / tags."""
    base = dict(
        id="evt-1",
        source="infra-monitor",
        timestamp="2026-08-23T09:00:00Z",
        event_type="high_cpu",
        severity="critical",
        service="payment-api",
        environment="production",
        region="ap-south",
        title="CPU usage at 95%",
        description="Sustained CPU saturation on primary pods.",
        details={
            "metric_name": "cpu_utilization_percent",
            "metric_value": 95,
            "threshold": 80,
        },
        tags=["infrastructure", "performance"],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def make_ranking(rank=1, score=0.87):
    """Shape produced by backend/app/services/ranking.py::rank_events."""
    return {
        "event": None,
        "rank": rank,
        "score": score,
        "priority_score": score,
        "score_breakdown": {
            "severity": 0.30,
            "frequency": 0.10,
            "recency": 0.12,
            "anomaly": 0.18,
            "business_impact": 0.15,
        },
    }


def make_legacy_flat_scores(rank=2):
    """Pre-harmonisation flat vocabulary — must stay tolerated (read-only)."""
    return {
        "rank": rank,
        "final_score": 88.4,
        "severity_score": 100.0,
        "anomaly_score": 82.0,
        "recurrence_score": 65.0,
    }


VALID_LLM_TEXT = json.dumps(
    {
        "summary": "Payment API CPU saturation in ap-south.",
        "why_prioritized": (
            "It ranked #1 from severity 0.30 and anomaly 0.18 weighted contributions."
        ),
        "recommended_action": "Scale out payment-api pods now.",
    }
)


def patch_ollama_client(monkeypatch, handler):
    """Route explainer's httpx.AsyncClient through a MockTransport."""
    calls = []
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        calls.append(kwargs)
        return real_client(transport=httpx.MockTransport(handler), timeout=kwargs.get("timeout"))

    monkeypatch.setattr(explainer.httpx, "AsyncClient", factory)
    return calls


def ok_handler(text):
    def handler(request):
        return httpx.Response(200, json={"response": text})

    return handler


def failing_handler(exc_factory):
    def handler(request):
        raise exc_factory(request)

    return handler


TEMPLATE_MARKER = "by the scoring engine"
CONTRACT_KEYS = {"summary", "why_prioritized", "recommended_action", "provider"}


def assert_contract(data):
    assert set(data.keys()) == CONTRACT_KEYS
    assert all(isinstance(v, str) and v.strip() for v in data.values())
    assert data["provider"] in ("ollama", "fallback")


# ---------------------------------------------------------------------------
# LLM success paths
# ---------------------------------------------------------------------------


async def test_successful_llm_explanation(monkeypatch):
    calls = patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    data = await explainer.generate_explanation(make_event(), make_ranking())

    assert len(calls) == 1
    assert_contract(data)
    assert data["provider"] == "ollama"
    assert data["summary"].startswith("Payment API CPU saturation")
    assert data["recommended_action"] == "Scale out payment-api pods now."
    assert TEMPLATE_MARKER not in data["why_prioritized"]


async def test_structured_output_has_exact_schema(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    data = await explainer.generate_structured_explanation(make_event(), make_ranking())

    assert_contract(data)
    assert data["provider"] == "ollama"


async def test_request_body_uses_json_mode_and_no_think(monkeypatch):
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": VALID_LLM_TEXT})

    patch_ollama_client(monkeypatch, handler)
    await explainer.generate_explanation(make_event(), make_ranking())

    body = captured["body"]
    assert body["format"] == "json"
    assert body["think"] is False
    assert body["stream"] is False
    assert "AIOps operations assistant" in body["prompt"]
    assert "Rank: #1" in body["prompt"]
    assert "host.docker.internal" not in captured.get("url", "")


async def test_prompt_contains_actual_five_signal_breakdown():
    prompt = explainer.build_prompt(make_event(), make_ranking(score=0.87))

    assert "Never change rankings" in prompt
    assert "Rank: #1" in prompt
    assert "Priority Score: 0.87 (scale 0.0-1.0)" in prompt
    assert "severity=0.30" in prompt
    assert "frequency=0.10" in prompt
    assert "recency=0.12" in prompt
    assert "anomaly=0.18" in prompt
    assert "business_impact=0.15" in prompt
    assert "infra-monitor" in prompt
    assert "payment-api" in prompt
    assert '"recommended_action"' in prompt


async def test_prompt_surfaces_relevant_details_and_tags():
    prompt = explainer.build_prompt(make_event(), make_ranking())
    assert "cpu_utilization_percent" in prompt
    assert "Tags: infrastructure, performance" in prompt


async def test_markdown_fenced_json_still_parses(monkeypatch):
    fenced = "```json\n" + VALID_LLM_TEXT + "\n```"
    patch_ollama_client(monkeypatch, ok_handler(fenced))
    data = await explainer.generate_explanation(make_event(), make_ranking())
    assert data["provider"] == "ollama"
    assert data["summary"].startswith("Payment API CPU saturation")


# ---------------------------------------------------------------------------
# Failure -> fallback paths (same structure, provider=fallback)
# ---------------------------------------------------------------------------


async def test_ollama_unreachable_falls_back_and_breaks_circuit(monkeypatch):
    calls = patch_ollama_client(
        monkeypatch,
        failing_handler(lambda req: httpx.ConnectError("connection refused", request=req)),
    )

    data = await explainer.generate_explanation(make_event(), make_ranking())
    assert_contract(data)
    assert data["provider"] == "fallback"
    assert TEMPLATE_MARKER in data["why_prioritized"]

    # Circuit breaker: the immediate retry must not hit HTTP again.
    await explainer.generate_explanation(make_event(), make_ranking())
    assert len(calls) == 1


async def test_timeout_falls_back(monkeypatch):
    patch_ollama_client(
        monkeypatch,
        failing_handler(lambda req: httpx.ReadTimeout("timed out", request=req)),
    )
    data = await explainer.generate_explanation(make_event(), make_ranking())

    assert data["provider"] == "fallback"
    assert data["recommended_action"]  # deterministic action still supplied


async def test_http_error_falls_back(monkeypatch):
    patch_ollama_client(
        monkeypatch,
        failing_handler(lambda req: httpx.HTTPStatusError(
            "boom", request=req,
            response=httpx.Response(500, request=req),
        )),
    )
    data = await explainer.generate_explanation(make_event(), make_ranking())
    assert data["provider"] == "fallback"


async def test_malformed_non_json_response_falls_back(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler("Sorry, the payment api seems bad overall."))
    data = await explainer.generate_structured_explanation(make_event(), make_ranking())
    assert data["provider"] == "fallback"
    assert TEMPLATE_MARKER in data["why_prioritized"]


async def test_json_with_missing_keys_falls_back(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(json.dumps({"text": "hi", "foo": "bar"})))
    data = await explainer.generate_structured_explanation(make_event(), make_ranking())
    assert data["provider"] == "fallback"
    assert TEMPLATE_MARKER in data["why_prioritized"]


async def test_json_with_empty_fields_falls_back(monkeypatch):
    patch_ollama_client(
        monkeypatch,
        ok_handler(json.dumps({"summary": "", "why_prioritized": "x", "recommended_action": "y"})),
    )
    data = await explainer.generate_structured_explanation(make_event(), make_ranking())
    assert data["provider"] == "fallback"


async def test_disabled_flag_skips_ollama_entirely(monkeypatch):
    calls = patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    monkeypatch.setenv("OLLAMA_ENABLED", "false")

    data = await explainer.generate_explanation(make_event(), make_ranking())

    assert len(calls) == 0
    assert data["provider"] == "fallback"
    assert TEMPLATE_MARKER in data["why_prioritized"]


async def test_minimal_event_never_raises(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    data = await explainer.generate_explanation(SimpleNamespace(), {})
    assert_contract(data)
    assert data["provider"] == "fallback"


# ---------------------------------------------------------------------------
# Deterministic template categories (actual stream sources)
# ---------------------------------------------------------------------------


def test_template_infrastructure_monitor_stream():
    data = explainer.generate_template_structured(make_event(), make_ranking())
    assert_contract(data)
    assert data["provider"] == "fallback"
    assert "infrastructure alert" in data["summary"]
    assert "payment-api" in data["summary"]
    assert "cpu utilization percent at 95 exceeds threshold 80" in data["summary"]
    assert "autoscaling" in data["recommended_action"]


def test_template_app_errors_stream():
    event = make_event(
        source="app-errors",
        event_type="http_500_spike",
        title="HTTP 500 spike on checkout",
        description="Error rate jumped.",
        details={"error_type": "http_500", "error_rate_percent": 12},
    )
    data = explainer.generate_template_structured(event, make_ranking(rank=2))

    assert "application error" in data["summary"]
    assert "http 500" in data["summary"]
    assert "12% error rate" in data["summary"]
    assert "Ranked #2" in data["why_prioritized"]
    assert "error logs" in data["recommended_action"]


def test_template_deploy_events_stream():
    event = make_event(
        source="deploy-events",
        event_type="deploy_failed",
        severity="warning",
        service="cart-checkout",
        region="eu-west",
        title="Deploy failed",
        description="Rollout unhealthy.",
        details={
            "deploy_type": "rolling_update",
            "version_to": "2.14.0",
            "failure_reason": "health check failed",
        },
    )
    data = explainer.generate_template_structured(event, make_ranking(rank=3))

    assert "deployment incident" in data["summary"]
    assert "rolling update to 2.14.0" in data["summary"]
    assert "health check failed" in data["summary"]
    assert "rollback" in data["recommended_action"]


def test_template_security_keywords():
    event = make_event(
        source="app-errors",
        event_type="failed_login_burst",
        title="Failed login burst from single IP",
        severity="warning",
        details={"failed_attempts": 40},
    )
    data = explainer.generate_template_structured(event, make_ranking())

    assert "security incident" in data["summary"]
    assert "authentication logs" in data["recommended_action"]


def test_template_generic_event():
    event = make_event(
        source="telemetry",
        event_type="odd_pattern",
        title="Unusual behaviour noticed",
        severity="low",
        details={},
    )
    data = explainer.generate_template_structured(event, make_ranking())
    assert "operational event" in data["summary"]


def test_template_non_production_environment_shown():
    event = make_event(environment="staging")
    data = explainer.generate_template_structured(event, make_ranking())
    assert "staging (ap-south)" in data["summary"]


def test_template_reports_supplied_contributions_verbatim():
    data = explainer.generate_template_structured(make_event(), make_ranking(rank=3))

    wp = data["why_prioritized"]
    assert "Ranked #3 by the scoring engine (score 0.87)" in wp
    assert "severity 0.30" in wp          # strongest signal first, verbatim
    assert "anomaly 0.18" in wp           # second
    assert "business_impact 0.15" in wp   # third
    assert "strongest signal: severity" in wp
    assert "critical severity" in wp


def test_template_tolerates_legacy_flat_scores():
    data = explainer.generate_template_structured(make_event(), make_legacy_flat_scores())

    wp = data["why_prioritized"]
    assert "Ranked #2" in wp
    assert "88.40" in wp  # final_score consumed verbatim
    assert "anomaly 82.00" in wp
    assert data["provider"] == "fallback"


# ---------------------------------------------------------------------------
# Contract safety & adapters
# ---------------------------------------------------------------------------


async def test_ranking_input_is_never_mutated(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    ranking = make_ranking(rank=3)
    snapshot = copy.deepcopy(ranking)

    await explainer.generate_explanation(make_event(), ranking)

    assert ranking == snapshot


async def test_pair_adapter_matches_two_value_signature(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    explanation, action = await explainer.generate_explanation_pair(
        make_event(), make_ranking()
    )

    assert explanation.startswith("Payment API CPU saturation")
    assert action == "Scale out payment-api pods now."


async def test_trio_adapter_maps_provider_to_explanation_type(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    explanation, exp_type, action = await explainer.generate_explanation_trio(
        make_event(), make_ranking()
    )
    assert exp_type == "ai"
    assert explanation and action

    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    fb_explanation, fb_type, fb_action = await explainer.generate_explanation_trio(
        make_event(), make_ranking()
    )
    assert fb_type == "template"
    assert fb_explanation and fb_action


async def test_batch_helper_attaches_only_top_n_and_preserves_order(monkeypatch):
    calls = patch_ollama_client(
        monkeypatch,
        failing_handler(lambda req: httpx.ConnectError("refused", request=req)),
    )
    items = [
        {"event": make_event(id=f"e{i}"), "rank": i, "score": 0.9 - i * 0.01}
        for i in range(1, 4)
    ]

    await explainer.generate_explanations_for_ranked(items, top_n=1)

    assert len(calls) == 1  # circuit breaker after the first failure
    assert items[0]["explanation_provider"] == "fallback"
    assert items[0]["explanation"] and items[0]["suggested_action"]
    assert "explanation" not in items[1] and "explanation" not in items[2]
    assert [it["rank"] for it in items] == [1, 2, 3]  # ordering untouched


async def test_dict_shaped_events_supported(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    event = {
        "id": "evt-9",
        "source": "app-errors",
        "event_type": "payment_latency",
        "severity": "critical",
        "service": "gateway",
        "environment": "production",
        "region": "eu-west",
        "title": "P99 latency breach",
        "description": "p99 above 2s.",
        "details": {"error_rate_percent": 9},
        "tags": ["payments"],
    }
    data = await explainer.generate_explanation(event, make_ranking())
    assert_contract(data)
    assert data["provider"] == "ollama"


def test_legacy_alias_fields_still_supported():
    """Old-style stream_source/raw_payload objects keep working."""
    event = SimpleNamespace(
        stream_source="app-errors",
        raw_payload={"error_type": "exception_burst"},
        event_type="exception_burst",
        severity="high",
        service="user-service",
        environment="production",
        region="us-east",
        title="Exception burst",
        description="",
    )
    data = explainer.generate_template_structured(event, make_ranking())
    assert "application error" in data["summary"]
