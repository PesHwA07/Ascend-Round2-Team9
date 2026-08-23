"""Gen-AI explainer tests.

No live Ollama server required: every HTTP interaction is mocked with
httpx.MockTransport. Ranking data is consumed verbatim and asserted immutable.
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
    return {
        "event": None,
        "rank": rank,
        "priority_score": priority,
        "severity_score": 100.0,
        "blast_radius_score": 70.0,
        "anomaly_score": 82.0,
        "recurrence_score": 65.0,
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


# ---------------------------------------------------------------------------
# LLM success paths
# ---------------------------------------------------------------------------


async def test_successful_llm_explanation(monkeypatch):
    calls = patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    explanation, action = await explainer.generate_explanation(make_event(), make_scores())

    assert len(calls) == 1
    assert explanation.startswith("Payment API CPU saturation in ap-south.")
    assert action == "Scale out payment-api pods now."
    assert TEMPLATE_MARKER not in explanation


async def test_structured_output_has_exact_schema(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    data = await explainer.generate_structured_explanation(make_event(), make_scores())

    assert set(data.keys()) == {"summary", "why_prioritized", "recommended_action"}
    assert all(isinstance(v, str) and v.strip() for v in data.values())


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


# ---------------------------------------------------------------------------
# Failure -> fallback paths
# ---------------------------------------------------------------------------


async def test_ollama_unreachable_falls_back_and_breaks_circuit(monkeypatch):
    calls = patch_ollama_client(
        monkeypatch,
        failing_handler(lambda req: httpx.ConnectError("connection refused", request=req)),
    )

    explanation, action = await explainer.generate_explanation(make_event(), make_scores())
    assert TEMPLATE_MARKER in explanation
    assert "payment-api" in explanation

    # Circuit breaker: the immediate retry must not hit HTTP again.
    await explainer.generate_explanation(make_event(), make_scores())
    assert len(calls) == 1


async def test_timeout_falls_back(monkeypatch):
    patch_ollama_client(
        monkeypatch,
        failing_handler(lambda req: httpx.ReadTimeout("timed out", request=req)),
    )
    explanation, action = await explainer.generate_explanation(make_event(), make_scores())

    assert TEMPLATE_MARKER in explanation
    assert action  # deterministic action text still supplied


async def test_http_error_falls_back(monkeypatch):
    patch_ollama_client(
        monkeypatch,
        failing_handler(lambda req: httpx.HTTPStatusError(
            "boom", request=req,
            response=httpx.Response(500, request=req),
        )),
    )
    explanation, _ = await explainer.generate_explanation(make_event(), make_scores())
    assert TEMPLATE_MARKER in explanation


async def test_malformed_non_json_response_falls_back(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler("Sorry, the payment api seems bad overall."))
    data = await explainer.generate_structured_explanation(make_event(), make_scores())

    assert TEMPLATE_MARKER in data["why_prioritized"]


async def test_json_with_missing_keys_falls_back(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(json.dumps({"text": "hi", "foo": "bar"})))
    data = await explainer.generate_structured_explanation(make_event(), make_scores())

    assert set(data.keys()) == {"summary", "why_prioritized", "recommended_action"}
    assert TEMPLATE_MARKER in data["why_prioritized"]


async def test_json_with_empty_fields_falls_back(monkeypatch):
    patch_ollama_client(
        monkeypatch,
        ok_handler(json.dumps({"summary": "", "why_prioritized": "x", "recommended_action": "y"})),
    )
    data = await explainer.generate_structured_explanation(make_event(), make_scores())
    assert TEMPLATE_MARKER in data["why_prioritized"]


async def test_markdown_fenced_json_still_parses(monkeypatch):
    fenced = "```json\n" + VALID_LLM_TEXT + "\n```"
    patch_ollama_client(monkeypatch, ok_handler(fenced))
    explanation, action = await explainer.generate_explanation(make_event(), make_scores())
    assert explanation.startswith("Payment API CPU saturation")
    assert action == "Scale out payment-api pods now."


def test_disabled_flag_skips_ollama_entirely(monkeypatch):
    calls = patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    monkeypatch.setenv("OLLAMA_ENABLED", "false")

    explanation, _ = explainer.generate_template_explanation(make_event(), make_scores())

    assert len(calls) == 0
    assert TEMPLATE_MARKER in explanation


# ---------------------------------------------------------------------------
# Template fallback categories
# ---------------------------------------------------------------------------


def test_template_infrastructure_event():
    explanation, action = explainer.generate_template_explanation(
        make_event(), make_scores()
    )
    assert "infrastructure incident" in explanation
    assert "payment-api" in explanation
    assert "ap-south" in explanation
    assert "82/100" in explanation  # anomaly score surfaced verbatim
    assert "autoscaling" in action


def test_template_application_error_event():
    event = make_event(
        stream_source="app_business",
        event_type="http_500_spike",
        title="HTTP 500 spike on checkout",
        description="Error rate jumped to 12%.",
    )
    explanation, action = explainer.generate_template_explanation(event, make_scores(rank=2))

    assert "application incident" in explanation
    assert "HTTP 500 spike on checkout" in explanation
    assert "Ranked #2" in explanation
    assert "error logs" in action


def test_template_deployment_event():
    event = make_event(
        stream_source="app_business",
        event_type="deploy_failed",
        title="Deploy failed for release 2.14",
        severity="high",
    )
    explanation, action = explainer.generate_template_explanation(event, make_scores())

    assert "deployment-related incident" in explanation
    assert "release 2.14" in explanation
    assert "rollback" in action


def test_template_security_event():
    event = make_event(
        stream_source="auth_security",
        event_type="failed_login_burst",
        title="Failed login burst from single IP",
        severity="high",
    )
    explanation, action = explainer.generate_template_explanation(event, make_scores())

    assert "security incident" in explanation
    assert "Failed login burst" in explanation
    assert "authentication logs" in action


def test_template_generic_event():
    event = make_event(
        stream_source="telemetry",
        event_type="odd_pattern",
        title="Unusual behaviour noticed",
        severity="low",
    )
    explanation, _ = explainer.generate_template_explanation(event, make_scores())

    assert "operational event" in explanation


def test_template_non_production_environment_shown():
    event = make_event(environment="staging")
    explanation, _ = explainer.generate_template_explanation(event, make_scores())
    assert "staging (ap-south)" in explanation


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


async def test_ranking_input_is_never_mutated(monkeypatch):
    patch_ollama_client(monkeypatch, ok_handler(VALID_LLM_TEXT))
    scores = make_scores(rank=3)
    snapshot = copy.deepcopy(scores)

    await explainer.generate_explanation(make_event(), scores)

    assert scores == snapshot


async def test_minimal_event_never_raises():
    explanation, action = await explainer.generate_explanation(SimpleNamespace(), {})
    assert isinstance(explanation, str) and explanation
    assert isinstance(action, str) and action


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
    explanation, action = await explainer.generate_explanation(event, make_scores())
    assert explanation and action
