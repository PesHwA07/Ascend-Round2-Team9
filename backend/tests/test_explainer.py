"""Gen-AI explainer tests.

No live Ollama server required: every HTTP interaction is mocked with
httpx.MockTransport. Ranking data is consumed verbatim and asserted immutable.

Agreed contract:
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
    base = dict(
        id="evt-1",
        stream_source="infra_apm",
        event_type="high_cpu",
        severity="critical",
        service="payment-api",
        environment="production",
        region="ap-south",
        title="CPU usage at 95%",
        description="Sustained CPU saturation on primary pods.",
        raw_payload={"tags": ["infrastructure", "performance"]},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def make_scores(rank=1, priority=87.5):
    """Shape produced by backend/app/services/ranking.py::rank_events."""
    return {
        "event": None,
        "rank": rank,
        "priority_score": priority,
        "severity_score": 100.0,
        "blast_radius_score": 70.0,
        "anomaly_score": 82.0,
        "recurrence_score": 65.0,
    }


def make_prd_scores(rank=1):
    """PRD-style vocabulary the explainer must also tolerate (read-only)."""
    return {
        "rank": rank,
        "final_score": 88.4,
        "severity_score": 100.0,
        "frequency_score": 70.0,
        "recency_score": 80.0,
        "anomaly_score": 82.0,
        "business_impact_score": 65.0,
    }


VALID_LLM_TEXT = json.dumps(
    {
        "summary": "Payment API CPU saturation in ap-south.",
        "why_prioritized": "It ranked #1 from critical severity and high anomaly.",
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
    data = await explainer.generate_explanation(make_event(), make_scores())

    assert len(calls) == 1
    assert_contract(data)
    assert data["provider"] == "ollama"
    assert data["summary"].startswith("Payment API CPU saturation")
    assert data["recommended_action"] == "Scale out payment-api pods now."
    assert TEMPLATE_MARKER not in data["why_prioritized"]


async def test_structured_output_has_exact_schema(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    data = await explainer.generate_structured_explanation(make_event(), make_scores())

    assert_contract(data)
    assert data["provider"] == "ollama"


async def test_request_body_uses_json_mode_and_no_think(monkeypatch):
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": VALID_LLM_TEXT})

    patch_ollama_client(monkeypatch, handler)
    await explainer.generate_explanation(make_event(), make_scores())

    body = captured["body"]
    assert body["format"] == "json"
    assert body["think"] is False
    assert body["stream"] is False
    assert "AIOps operations assistant" in body["prompt"]
    assert "Rank: #1" in body["prompt"]


async def test_markdown_fenced_json_still_parses(monkeypatch):
    fenced = "```json\n" + VALID_LLM_TEXT + "\n```"
    patch_ollama_client(monkeypatch, ok_handler(fenced))
    data = await explainer.generate_explanation(make_event(), make_scores())
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

    data = await explainer.generate_explanation(make_event(), make_scores())
    assert_contract(data)
    assert data["provider"] == "fallback"
    assert TEMPLATE_MARKER in data["why_prioritized"]

    # Circuit breaker: the immediate retry must not hit HTTP again.
    await explainer.generate_explanation(make_event(), make_scores())
    assert len(calls) == 1


async def test_timeout_falls_back(monkeypatch):
    patch_ollama_client(
        monkeypatch,
        failing_handler(lambda req: httpx.ReadTimeout("timed out", request=req)),
    )
    data = await explainer.generate_explanation(make_event(), make_scores())

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
    data = await explainer.generate_explanation(make_event(), make_scores())
    assert data["provider"] == "fallback"


async def test_malformed_non_json_response_falls_back(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler("Sorry, the payment api seems bad overall."))
    data = await explainer.generate_structured_explanation(make_event(), make_scores())
    assert data["provider"] == "fallback"
    assert TEMPLATE_MARKER in data["why_prioritized"]


async def test_json_with_missing_keys_falls_back(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(json.dumps({"text": "hi", "foo": "bar"})))
    data = await explainer.generate_structured_explanation(make_event(), make_scores())
    assert data["provider"] == "fallback"
    assert TEMPLATE_MARKER in data["why_prioritized"]


async def test_json_with_empty_fields_falls_back(monkeypatch):
    patch_ollama_client(
        monkeypatch,
        ok_handler(json.dumps({"summary": "", "why_prioritized": "x", "recommended_action": "y"})),
    )
    data = await explainer.generate_structured_explanation(make_event(), make_scores())
    assert data["provider"] == "fallback"


async def test_disabled_flag_skips_ollama_entirely(monkeypatch):
    calls = patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    monkeypatch.setenv("OLLAMA_ENABLED", "false")

    data = await explainer.generate_explanation(make_event(), make_scores())

    assert len(calls) == 0
    assert data["provider"] == "fallback"
    assert TEMPLATE_MARKER in data["why_prioritized"]


async def test_minimal_event_never_raises(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    data = await explainer.generate_explanation(SimpleNamespace(), {})
    assert_contract(data)
    assert data["provider"] == "fallback"


# ---------------------------------------------------------------------------
# Deterministic template categories
# ---------------------------------------------------------------------------


def test_template_infrastructure_event():
    data = explainer.generate_template_structured(make_event(), make_scores())
    assert_contract(data)
    assert data["provider"] == "fallback"
    assert "infrastructure incident" in data["summary"]
    assert "payment-api" in data["summary"]
    assert "ap-south" in data["summary"]
    assert "82/100" in data["why_prioritized"]  # anomaly score surfaced verbatim
    assert "autoscaling" in data["recommended_action"]


def test_template_application_error_event():
    event = make_event(
        stream_source="app_business",
        event_type="http_500_spike",
        title="HTTP 500 spike on checkout",
        description="Error rate jumped to 12%.",
    )
    data = explainer.generate_template_structured(event, make_scores(rank=2))

    assert "application incident" in data["summary"]
    assert "HTTP 500 spike on checkout" in data["summary"]
    assert "Ranked #2" in data["why_prioritized"]
    assert "error logs" in data["recommended_action"]


def test_template_deployment_event():
    event = make_event(
        stream_source="app_business",
        event_type="deploy_failed",
        title="Deploy failed for release 2.14",
        severity="high",
    )
    data = explainer.generate_template_structured(event, make_scores())

    assert "deployment-related incident" in data["summary"]
    assert "release 2.14" in data["summary"]
    assert "rollback" in data["recommended_action"]


def test_template_security_event():
    event = make_event(
        stream_source="auth_security",
        event_type="failed_login_burst",
        title="Failed login burst from single IP",
        severity="high",
    )
    data = explainer.generate_template_structured(event, make_scores())

    assert "security incident" in data["summary"]
    assert "Failed login burst" in data["summary"]
    assert "authentication logs" in data["recommended_action"]


def test_template_generic_event():
    event = make_event(
        stream_source="telemetry",
        event_type="odd_pattern",
        title="Unusual behaviour noticed",
        severity="low",
    )
    data = explainer.generate_template_structured(event, make_scores())
    assert "operational event" in data["summary"]


def test_template_non_production_environment_shown():
    event = make_event(environment="staging")
    data = explainer.generate_template_structured(event, make_scores())
    assert "staging (ap-south)" in data["summary"]


def test_template_accepts_prd_style_scores():
    data = explainer.generate_template_structured(make_event(), make_prd_scores(rank=3))

    assert "Ranked #3" in data["why_prioritized"]
    assert "88/100" in data["why_prioritized"]  # final_score consumed verbatim
    assert "frequent recurrence" in data["why_prioritized"]
    assert "very recent occurrence" in data["why_prioritized"]
    assert "wide business impact" in data["why_prioritized"]
    assert data["provider"] == "fallback"


# ---------------------------------------------------------------------------
# Prompt & contract safety
# ---------------------------------------------------------------------------


def test_prompt_contains_ranking_context_and_rules():
    prompt = explainer.build_prompt(make_event(), make_scores(priority=91.25))

    assert "Never change rankings" in prompt
    assert "Rank: #1" in prompt
    assert "Priority Score: 91.25/100" in prompt
    assert "anomaly=82.0" in prompt
    assert "payment-api" in prompt
    assert '"recommended_action"' in prompt


def test_prompt_includes_optional_prd_factors_when_present():
    prompt = explainer.build_prompt(make_event(), make_prd_scores())
    assert "frequency=70" in prompt
    assert "recency=80" in prompt
    assert "business_impact=65" in prompt
    assert "Priority Score: 88.4/100" in prompt


def test_prompt_omits_absent_optional_factors():
    prompt = explainer.build_prompt(make_event(), make_scores())
    assert "Additional factors" not in prompt


async def test_ranking_input_is_never_mutated(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    scores = make_scores(rank=3)
    snapshot = copy.deepcopy(scores)

    await explainer.generate_explanation(make_event(), scores)

    assert scores == snapshot


async def test_pair_adapter_matches_legacy_router_signature(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    explanation, action = await explainer.generate_explanation_pair(
        make_event(), make_scores()
    )

    assert explanation.startswith("Payment API CPU saturation")
    assert action == "Scale out payment-api pods now."


async def test_batch_helper_attaches_only_top_n_and_preserves_order(monkeypatch):
    calls = patch_ollama_client(
        monkeypatch,
        failing_handler(lambda req: httpx.ConnectError("refused", request=req)),
    )
    items = [
        {"event": make_event(id=f"e{i}"), "rank": i, "priority_score": 90 - i}
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
        "stream_source": "app_business",
        "event_type": "payment_latency",
        "severity": "critical",
        "service": "payment-gateway",
        "environment": "production",
        "region": "eu-west",
        "title": "P99 latency breach",
        "description": "p99 above 2s.",
        "raw_payload": {},
    }
    data = await explainer.generate_explanation(event, make_scores())
    assert_contract(data)
    assert data["provider"] == "ollama"
