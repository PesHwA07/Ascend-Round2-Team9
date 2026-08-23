"""Gen-AI explanation layer for AuraBrief 95.

Architectural principle: **Ranking determines priority. Gen-AI explains the ranking.**

This service NEVER decides which incident is #1, NEVER reorders incidents,
NEVER recalculates scores and NEVER touches ranking weights. It consumes the
ranking engine's output verbatim and produces a short, operator-facing
explanation in the agreed contract shape:

    {
        "summary": "what happened",
        "why_prioritized": "why it received its current priority",
        "recommended_action": "what the operator should investigate first",
        "provider": "ollama" | "fallback",
    }

Primary provider : local Ollama (HTTP, JSON mode, no extra frameworks).
Fallback         : deterministic template explanations built from the same
                   event/ranking data (provider="fallback"), used whenever
                   Ollama is unavailable, errors, times out or returns an
                   invalid/malformed response — so the demo never breaks.

Input contract (matches backend/app/services/ranking.py::rank_events):
    event        : ORM Event (or dict) — source/details/tags/timestamp/etc.
    ranking_data : {"event", "rank",
                    "score"/"priority_score": 0.0-1.0,
                    "score_breakdown": {"severity", "frequency", "recency",
                                        "anomaly", "business_impact"}}
Consumed strictly read-only; legacy flat-score dicts are still tolerated.

Public interface:
    await generate_explanation(event, ranking_data) -> contract dict above
    await generate_explanation_pair(event, ranking_data)
        -> (explanation_text, suggested_action)
    await generate_explanation_trio(event, ranking_data)
        -> (explanation_text, "ai"|"template", suggested_action)  # triage router
    await generate_explanations_for_ranked(ranked_items, top_n=N)
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional, Tuple

import httpx

PROVIDER_OLLAMA = "ollama"
PROVIDER_FALLBACK = "fallback"

logger = logging.getLogger("aurabrief.explainer")

# ---------------------------------------------------------------------------
# Configuration (env-first so this module is testable standalone; when the
# backend package is present we reuse its pydantic Settings instead).
# ---------------------------------------------------------------------------

_TRUTHY = {"1", "true", "yes", "on"}

_DEFAULTS = {
    "OLLAMA_ENABLED": "true",
    "OLLAMA_HOST": "http://localhost:11434",
    "OLLAMA_MODEL": "llama3.2:3b",
    "OLLAMA_TIMEOUT": "6.0",
    "OLLAMA_NUM_PREDICT": "150",
    "LLM_COOLDOWN_SECONDS": "60",
}


def _setting(name: str) -> str:
    """Resolve a Gen-AI setting: backend Settings -> env var -> default.

    Uses M5's ``OLLAMA_HOST`` convention.
    """
    try:
        from backend.app.config import settings  # teammate-owned config

        value = getattr(settings, name, None)
        if value is not None:
            return str(value)
    except Exception:
        pass
    return os.getenv(name, _DEFAULTS[name])


def _base_url() -> str:
    """Ollama endpoint via OLLAMA_HOST (backend convention).

    The backend's Docker-bridge default (``host.docker.internal``) is skipped
    when this module runs outside Docker; localhost is used instead.
    """
    candidates = [os.getenv("OLLAMA_HOST")]
    try:
        from backend.app.config import settings  # teammate-owned config

        candidates.append(getattr(settings, "OLLAMA_HOST", None))
    except Exception:
        pass
    for candidate in candidates:
        if candidate and "host.docker.internal" not in str(candidate):
            return str(candidate).rstrip("/")
    return _DEFAULTS["OLLAMA_HOST"]


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in _TRUTHY


# Circuit-breaker state: after an LLM failure, skip Ollama for a cooldown
# window so a batch of top-N items never queues behind repeated timeouts.
_state = {"cooldown_until": 0.0}


def llm_available() -> bool:
    if not _as_bool(_setting("OLLAMA_ENABLED")):
        return False
    return time.monotonic() >= _state["cooldown_until"]


def _start_cooldown() -> None:
    try:
        seconds = float(_setting("LLM_COOLDOWN_SECONDS"))
    except ValueError:
        seconds = 60.0
    _state["cooldown_until"] = time.monotonic() + max(0.0, seconds)


def reset_cooldown() -> None:
    """Used by tests (and hot reloads) to clear the circuit breaker."""
    _state["cooldown_until"] = 0.0


# ---------------------------------------------------------------------------
# Field access helpers (accepts ORM Event objects or plain dicts)
# ---------------------------------------------------------------------------


def _field(event: Any, name: str, default: Any = "") -> Any:
    if isinstance(event, dict):
        return event.get(name, default)
    return getattr(event, name, default)


def _event_details(event: Any) -> Dict[str, Any]:
    """Actual schema: ``Event.details`` (legacy alias ``raw_payload``)."""
    details = _field(event, "details", None)
    if details is None:
        details = _field(event, "raw_payload", {})
    if not isinstance(details, dict):
        return {}
    return details


def _event_tags(event: Any) -> list:
    tags = _field(event, "tags", None)
    if not isinstance(tags, (list, tuple)):
        tags = _event_details(event).get("tags") or []
    return list(tags)


def _event_source(event: Any) -> str:
    """Actual schema: ``source`` in {infra-monitor, app-errors, deploy-events}."""
    source = _field(event, "source", "") or _field(event, "stream_source", "")
    return str(source or "").lower()


def _num(ranking_data: Dict[str, Any], key: str) -> float:
    try:
        return float(ranking_data.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _headline_score(ranking_data: Dict[str, Any]) -> float:
    """The engine's final composite score, whichever key the caller supplies.

    Actual backend: ``score`` (aliased as ``priority_score``), 0.0-1.0.
    Read-only: never computed, never written back.
    """
    for key in ("score", "priority_score", "final_score"):
        if key in ranking_data:
            return _num(ranking_data, key)
    return 0.0


def _score_breakdown(ranking_data: Dict[str, Any]) -> Dict[str, float]:
    """Actual backend: weighted per-signal contributions in ``score_breakdown``.

    Values are consumed verbatim (they are component x weight results produced
    by the ranking engine). Legacy flat keys are tolerated when the breakdown
    dict is absent.
    """
    breakdown = ranking_data.get("score_breakdown")
    if isinstance(breakdown, dict):
        result = {}
        for key in ("severity", "frequency", "recency", "anomaly", "business_impact"):
            value = breakdown.get(key)
            if isinstance(value, (int, float)):
                result[key] = float(value)
        if result:
            return result

    # Legacy flat vocabulary (pre-harmonisation callers) — still read-only.
    legacy = {}
    for key in (
        "severity_score",
        "frequency_score",
        "recency_score",
        "anomaly_score",
        "business_impact_score",
        "blast_radius_score",
        "recurrence_score",
    ):
        if key in ranking_data:
            legacy[key.replace("_score", "")] = _num(ranking_data, key)
    return legacy


def _fmt_signal(value: float) -> str:
    return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """You are an AIOps operations assistant. An incident was ALREADY scored and ranked by a deterministic 5-signal engine. Explain that result to an on-call operator. Never change rankings, never recalculate scores, never invent facts or metrics not listed below.

INCIDENT (already ranked):
- Rank: #{rank}; Priority Score: {headline_score} (scale 0.0-1.0)
- Weighted signal contributions from the scoring engine: severity={severity}, frequency={frequency}, recency={recency}, anomaly={anomaly}, business_impact={business_impact}
- Severity: {severity_level}; Service: {service}; Environment: {environment}; Region: {region}
- Source stream: {source}; Type: {event_type}; Title: {title}
- Description: {description}{tags_line}{details_line}

OUTPUT RULES:
1. "summary": what happened (max 15 words).
2. "why_prioritized": why it ranked here; cite its rank number and reference at least two of the weighted contributions above exactly as given (max 20 words).
3. "recommended_action": the first investigation step (max 15 words).
4. Plain text only. Respond with ONLY valid JSON, no markdown:
{{"summary": "...", "why_prioritized": "...", "recommended_action": "..."}}"""


def build_prompt(event: Any, ranking_data: Dict[str, Any]) -> str:
    """Render the AIOps explanation prompt from existing event + ranking data.

    Values are consumed verbatim from ``ranking_data``/``event``; nothing is
    recalculated.
    """
    details = _event_details(event)
    tags = _event_tags(event)
    tags_line = f"\n- Tags: {', '.join(str(t) for t in tags)}" if tags else ""
    description = str(_field(event, "description", "") or "").strip()
    if len(description) > 200:
        description = description[:200] + "..."

    interesting = {
        k: details[k]
        for k in (
            "metric_name", "metric_value", "threshold", "error_type",
            "error_rate_percent", "deploy_type", "version_to",
        )
        if k in details
    }
    details_line = (
        f"\n- Key details: {json.dumps(interesting, default=str)}" if interesting else ""
    )

    breakdown = _score_breakdown(ranking_data)

    return _PROMPT_TEMPLATE.format(
        rank=int(_num(ranking_data, "rank") or 0),
        headline_score=_fmt_signal(_headline_score(ranking_data)),
        severity=_fmt_signal(breakdown.get("severity", 0.0)),
        frequency=_fmt_signal(breakdown.get("frequency", 0.0)),
        recency=_fmt_signal(breakdown.get("recency", 0.0)),
        anomaly=_fmt_signal(breakdown.get("anomaly", 0.0)),
        business_impact=_fmt_signal(breakdown.get("business_impact", 0.0)),
        severity_level=str(_field(event, "severity", "unknown")),
        service=str(_field(event, "service", "unknown-service")),
        environment=str(_field(event, "environment", "production")),
        region=str(_field(event, "region", "global")),
        source=_event_source(event) or "(unspecified)",
        event_type=str(_field(event, "event_type", "unknown")),
        title=str(_field(event, "title", "")).strip() or "(untitled)",
        description=description or "(none supplied)",
        tags_line=tags_line,
        details_line=details_line,
    )


# ---------------------------------------------------------------------------
# Ollama transport
# ---------------------------------------------------------------------------


async def call_ollama(prompt: str) -> str:
    """Call the local Ollama generate endpoint with a hard timeout.

    Raises on any transport/timeout/HTTP problem; callers own the fallback.
    """
    timeout = float(_setting("OLLAMA_TIMEOUT"))
    body = {
        "model": _setting("OLLAMA_MODEL"),
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_predict": int(float(_setting("OLLAMA_NUM_PREDICT"))),
        },
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{_base_url()}/api/generate", json=body)
        response.raise_for_status()
        return str(response.json().get("response", ""))


# ---------------------------------------------------------------------------
# Structured-output parsing / validation
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = ("summary", "why_prioritized", "recommended_action")
_MAX_FIELD_LEN = 400


def _extract_json_blob(raw: str) -> Optional[Dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def parse_explanation(raw: str) -> Optional[Dict[str, str]]:
    """Validate LLM output into exactly three non-empty string fields."""
    blob = _extract_json_blob(raw)
    if blob is None:
        return None
    cleaned: Dict[str, str] = {}
    for key in _REQUIRED_KEYS:
        value = blob.get(key)
        if not isinstance(value, (str, int, float)):
            return None
        text = str(value).strip()
        if not text:
            return None
        cleaned[key] = text[:_MAX_FIELD_LEN]
    return cleaned


# ---------------------------------------------------------------------------
# Deterministic template fallback
# ---------------------------------------------------------------------------


def _incident_category(event: Any) -> str:
    """Categorise from the actual stream names first, then keyword signals."""
    source = _event_source(event)
    etype = str(_field(event, "event_type", "")).lower()
    title = str(_field(event, "title", "")).lower()
    blob = f"{etype} {title}"

    if source == "deploy-events" or any(
        w in blob for w in ("deploy", "rollback", "release", "canary", "rollout", "migration")
    ):
        return "deployment"
    if source == "infra-monitor" or any(
        w in blob for w in ("cpu", "memory", "disk", "container", "pod", "node", "host", "infra", "oom")
    ):
        return "infrastructure"
    if any(
        w in blob for w in ("auth", "login", "security", "credential", "waf", "token")
    ):
        return "security"
    if source == "app-errors" or any(
        w in blob for w in (
            "error", "exception", "http", "500", "503", "latency", "timeout",
            "payment", "circuit", "crash", "checkout",
        )
    ):
        return "application_error"
    return "generic"


_ACTIONS = {
    "infrastructure": (
        "Check autoscaling and resource metrics for '{service}' in {region}, "
        "then inspect recent configuration or deployment changes."
    ),
    "application_error": (
        "Inspect '{service}' error logs and downstream dependencies in {region}; "
        "verify gateway timeouts and connection-pool health."
    ),
    "deployment": (
        "Review the latest '{service}' release in {environment} and prepare a rollback "
        "if error rates do not stabilise."
    ),
    "security": (
        "Review authentication logs for '{service}', check for credential abuse, "
        "and confirm rate-limit/WAF rules are active."
    ),
    "generic": (
        "Triage '{service}' logs and health endpoints in {region} and page the "
        "on-call owner if the signal persists."
    ),
}


def _why_prioritized(event: Any, ranking_data: Dict[str, Any]) -> str:
    """Describe the engine's supplied signal contributions — never recomputed.

    ``score_breakdown`` values are weighted contributions produced by the
    ranking engine. We surface the strongest ones verbatim; no weight values,
    normalisation or arithmetic beyond reading what was supplied.
    """
    breakdown = _score_breakdown(ranking_data)
    ordered = sorted(breakdown.items(), key=lambda kv: kv[1], reverse=True)

    rank = int(_num(ranking_data, "rank") or 0)
    headline = f"Ranked #{rank} by the scoring engine (score {_fmt_signal(_headline_score(ranking_data))})"

    if not ordered:
        return f"{headline} for its composite weighted score."

    leading = ", ".join(f"{name} {_fmt_signal(value)}" for name, value in ordered[:3])
    strongest = ordered[0][0].replace("_", " ")
    severity = str(_field(event, "severity", "unknown")).lower()
    severity_note = f" with {severity} severity" if severity in ("critical", "warning", "high") else ""

    return f"{headline}: leading contributions were {leading}{severity_note} (strongest signal: {strongest})."


def _summary_text(event: Any, category: str) -> str:
    severity = str(_field(event, "severity", "unknown")).upper()
    service = str(_field(event, "service", "unknown-service"))
    region = str(_field(event, "region", "global"))
    environment = str(_field(event, "environment", "production"))
    title = str(_field(event, "title", "")).strip()
    details = _event_details(event)
    location = f"{environment} ({region})" if environment != "production" else region

    labels = {
        "deployment": "deployment incident",
        "infrastructure": "infrastructure alert",
        "security": "security incident",
        "application_error": "application error",
        "generic": "operational event",
    }

    extra = ""
    if category == "infrastructure":
        metric = str(details.get("metric_name", "")).replace("_", " ").strip()
        if metric:
            value = details.get("metric_value", "?")
            threshold = details.get("threshold")
            extra = f": {metric} at {value}" + (
                f" exceeds threshold {threshold}" if threshold is not None else ""
            )
    elif category == "application_error":
        etype = str(details.get("error_type", "")).replace("_", " ").strip()
        rate = details.get("error_rate_percent")
        parts = [p for p in (etype, f"{rate}% error rate" if rate is not None else "") if p]
        if parts:
            extra = f": {', '.join(str(p) for p in parts)}"
    elif category == "deployment":
        dtype = str(details.get("deploy_type", "")).replace("_", " ").strip()
        version_to = details.get("version_to")
        reason = details.get("failure_reason")
        parts = [p for p in (dtype, f"to {version_to}" if version_to else "") if p]
        if parts:
            extra = f": {' '.join(str(p) for p in parts)}"
            if reason:
                extra += f"; reason: {reason}"

    return (
        f"{severity}: {labels[category]} on '{service}' in {location}"
        + (extra or (f": {title}" if title else ""))
        + "."
    )


def _template_structured(event: Any, ranking_data: Dict[str, Any]) -> Dict[str, str]:
    """Deterministic fallback in the exact contract shape (provider=fallback)."""
    category = _incident_category(event)
    service = str(_field(event, "service", "unknown-service"))
    region = str(_field(event, "region", "global"))
    environment = str(_field(event, "environment", "production"))

    summary = _summary_text(event, category)

    action_template = _ACTIONS.get(category, _ACTIONS["generic"])
    action = action_template.format(service=service, region=region, environment=environment)

    return {
        "summary": summary,
        "why_prioritized": _why_prioritized(event, ranking_data),
        "recommended_action": action,
        "provider": PROVIDER_FALLBACK,
    }


def generate_template_structured(
    event: Any, ranking_data: Dict[str, Any]
) -> Dict[str, str]:
    """Public deterministic fallback in the exact contract shape."""
    return _template_structured(event, ranking_data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_structured_explanation(
    event: Any, ranking_data: Dict[str, Any]
) -> Dict[str, str]:
    """Contract output via Ollama; guaranteed fallback on any failure.

    Returns exactly: summary, why_prioritized, recommended_action, provider.
    """
    if llm_available():
        try:
            prompt = build_prompt(event, ranking_data)
            raw = await call_ollama(prompt)
            parsed = parse_explanation(raw)
            if parsed is not None:
                parsed["provider"] = PROVIDER_OLLAMA
                logger.info(
                    "GenAI explanation via Ollama model=%s event=%s",
                    _setting("OLLAMA_MODEL"),
                    _field(event, "id", "?"),
                )
                return parsed
            logger.warning(
                "Ollama returned malformed explanation; using template fallback."
            )
        except Exception as exc:  # noqa: BLE001 - fallback must never be skipped
            logger.warning("Ollama unavailable (%r); using template fallback.", exc)
        _start_cooldown()

    return _template_structured(event, ranking_data)


async def generate_explanations_for_ranked(
    ranked_items: list, top_n: Optional[int] = None
) -> None:
    """Attach explanations to the ranking engine's output, concurrently.

    Consumes ``rank_events()`` output verbatim (list of dicts containing at
    least ``event`` and ``rank``). Adds ``explanation``, ``suggested_action``
    and ``explanation_provider`` keys to each top-N item in place; ordering
    and all ranking keys are never altered. Running the top-N calls
    concurrently keeps wall-clock time near a single LLM round-trip,
    protecting the 5-second end-to-end triage target.
    """
    targets = [item for item in ranked_items if top_n is None or item["rank"] <= top_n]
    if not targets:
        return
    results = await asyncio.gather(
        *(generate_explanation(item["event"], item) for item in targets)
    )
    for item, data in zip(targets, results):
        item["explanation"], item["suggested_action"] = _to_pair(data)
        item["explanation_provider"] = data["provider"]


def _to_pair(data: Dict[str, str]) -> Tuple[str, str]:
    """Flatten contract output into (explanation_text, suggested_action)."""
    return f"{data['summary']} {data['why_prioritized']}".strip(), data[
        "recommended_action"
    ]


async def generate_explanation(
    event: Any, ranking_data: Dict[str, Any]
) -> Dict[str, str]:
    """Agreed Gen-AI contract.

    Input : ``event`` (ORM Event or dict) and ``ranking_data`` (the ranking
            engine's per-item result, consumed read-only).
    Output: {"summary", "why_prioritized", "recommended_action",
             "provider": "ollama" | "fallback"}

    Never raises; never mutates ``ranking_data``; never recomputes scores.
    """
    try:
        return await generate_structured_explanation(event, ranking_data)
    except Exception as exc:  # absolute last-resort guard
        logger.error("Explainer unexpectedly failed (%r); minimal fallback used.", exc)
        service = str(_field(event, "service", "unknown-service"))
        rank = int(_num(ranking_data, "rank") or 0)
        return {
            "summary": f"Incident on '{service}' ranked #{rank}.",
            "why_prioritized": (
                f"Ranked #{rank} by the scoring engine; explanation "
                f"temporarily unavailable."
            ),
            "recommended_action": (
                f"Triage '{service}' logs and follow standard on-call procedure."
            ),
            "provider": PROVIDER_FALLBACK,
        }


async def generate_explanation_pair(
    event: Any, ranking_data: Dict[str, Any]
) -> Tuple[str, str]:
    """Adapter returning ``(explanation_text, suggested_action)``.

    Thin wrapper over :func:`generate_explanation`; same guarantees apply.
    """
    return _to_pair(await generate_explanation(event, ranking_data))


def _provider_to_type(provider: str) -> str:
    """Map contract providers onto TriageItem.explanation_type values."""
    return "ai" if provider == PROVIDER_OLLAMA else "template"


async def generate_explanation_trio(
    event: Any, ranking_data: Dict[str, Any]
) -> Tuple[str, str, str]:
    """Adapter matching the actual triage-router unpack.

    Returns ``(explanation, explanation_type, suggested_action)`` where
    ``explanation_type`` is ``"ai"`` for Ollama output and ``"template"``
    for fallback — exactly what ``routers/triage.py`` persists on TriageItem.
    """
    data = await generate_explanation(event, ranking_data)
    explanation = f"{data['summary']} {data['why_prioritized']}".strip()
    return explanation, _provider_to_type(data["provider"]), data["recommended_action"]
