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

Public interface:
    await generate_explanation(event, ranking_data) -> contract dict above
    await generate_explanation_pair(event, ranking_data)
        -> (explanation_text, suggested_action)  # legacy triage-router shape
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
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "llama3.2:3b",
    "OLLAMA_TIMEOUT": "6.0",
    "OLLAMA_NUM_PREDICT": "150",
    "LLM_COOLDOWN_SECONDS": "60",
}


def _setting(name: str) -> str:
    """Resolve a Gen-AI setting: backend Settings -> env var -> default."""
    try:
        from backend.app.config import settings  # teammate-owned config

        value = getattr(settings, name, None)
        if value is not None:
            return str(value)
    except Exception:
        pass
    return os.getenv(name, _DEFAULTS[name])


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


def _num(ranking_data: Dict[str, Any], key: str) -> float:
    try:
        return float(ranking_data.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _headline_score(ranking_data: Dict[str, Any]) -> float:
    """The engine's final composite score, whichever key the caller supplies.

    Supports ``priority_score`` (current backend) and ``final_score`` (PRD
    wording). Read-only: never computed, never written back.
    """
    if "priority_score" in ranking_data:
        return _num(ranking_data, "priority_score")
    return _num(ranking_data, "final_score")


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """You are an AIOps operations assistant. An incident was ALREADY scored and ranked by a deterministic engine. Explain that result to an on-call operator. Never change rankings, never recalculate scores, never invent facts or metrics not listed below.

INCIDENT (already ranked):
- Rank: #{rank}; Priority Score: {headline_score}/100
- Breakdown: severity={severity_score}, blast_radius={blast_radius_score}, anomaly={anomaly_score}, recurrence={recurrence_score} (each /100){extra_scores_line}
- Severity: {severity}; Service: {service}; Environment: {environment}; Region: {region}
- Type: {event_type}; Title: {title}
- Description: {description}{tags_line}

OUTPUT RULES:
1. "summary": what happened (max 15 words).
2. "why_prioritized": why it ranked here; cite its rank number plus two score values (max 20 words).
3. "recommended_action": the first investigation step (max 15 words).
4. Plain text only. Respond with ONLY valid JSON, no markdown:
{{"summary": "...", "why_prioritized": "...", "recommended_action": "..."}}"""


def build_prompt(event: Any, ranking_data: Dict[str, Any]) -> str:
    """Render the AIOps explanation prompt from existing event + ranking data.

    Values are consumed verbatim from ``ranking_data``; nothing is recalculated.
    Optional PRD-style component scores (frequency/recency/business impact) are
    included only when the caller supplied them.
    """
    payload = _field(event, "raw_payload", {}) or {}
    if not isinstance(payload, dict):
        payload = {}
    tags = payload.get("tags") or []
    tags_line = f"\n- Tags: {', '.join(str(t) for t in tags)}" if tags else ""
    description = str(_field(event, "description", "") or "").strip()
    if len(description) > 200:
        description = description[:200] + "..."

    extras = []
    for key in ("frequency_score", "recency_score", "business_impact_score"):
        if key in ranking_data:
            extras.append(f"{key.replace('_score', '')}={_num(ranking_data, key):.0f}")
    extra_scores_line = f"\n- Additional factors: {', '.join(extras)}" if extras else ""

    return _PROMPT_TEMPLATE.format(
        rank=int(_num(ranking_data, "rank") or 0),
        headline_score=_headline_score(ranking_data),
        severity_score=_num(ranking_data, "severity_score"),
        blast_radius_score=_num(ranking_data, "blast_radius_score"),
        anomaly_score=_num(ranking_data, "anomaly_score"),
        recurrence_score=_num(ranking_data, "recurrence_score"),
        extra_scores_line=extra_scores_line,
        severity=str(_field(event, "severity", "unknown")),
        service=str(_field(event, "service", "unknown-service")),
        environment=str(_field(event, "environment", "production")),
        region=str(_field(event, "region", "global")),
        event_type=str(_field(event, "event_type", "unknown")),
        title=str(_field(event, "title", "")).strip() or "(untitled)",
        description=description or "(none supplied)",
        tags_line=tags_line,
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
        response = await client.post(
            f"{_setting('OLLAMA_BASE_URL').rstrip('/')}/api/generate", json=body
        )
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
    etype = str(_field(event, "event_type", "")).lower()
    source = str(_field(event, "stream_source", "")).lower()
    title = str(_field(event, "title", "")).lower()
    blob = f"{etype} {source} {title}"

    deploy_words = (
        "deploy", "rollback", "release", "canary", "rollout", "migration", "config change"
    )
    infra_words = (
        "cpu", "memory", "disk", "container", "pod", "node", "host", "infra", "oom",
    )
    security_words = ("auth", "login", "security", "credential", "waf", "token")
    app_words = (
        "error", "exception", "http", "500", "503", "latency", "timeout", "payment",
        "circuit", "crash", "checkout",
    )
    if any(word in blob for word in deploy_words):
        return "deployment"
    if any(word in blob for word in infra_words):
        return "infrastructure"
    if any(word in blob for word in security_words):
        return "security"
    if any(word in blob for word in app_words):
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
    reasons = []
    severity = str(_field(event, "severity", "unknown")).lower()
    if severity in ("critical", "high"):
        reasons.append(f"{severity} severity")

    anomaly = _num(ranking_data, "anomaly_score")
    if anomaly >= 60:
        reasons.append(f"elevated anomaly score ({anomaly:.0f}/100)")
    elif anomaly >= 35:
        reasons.append(f"moderate anomaly score ({anomaly:.0f}/100)")

    blast = _num(ranking_data, "blast_radius_score")
    business_impact = _num(ranking_data, "business_impact_score")
    if max(blast, business_impact) >= 60:
        label = "business impact" if business_impact >= blast else "blast radius"
        reasons.append(f"wide {label} ({max(blast, business_impact):.0f}/100)")

    recurrence = _num(ranking_data, "recurrence_score")
    frequency = _num(ranking_data, "frequency_score")
    recency = _num(ranking_data, "recency_score")
    if max(recurrence, frequency) >= 60:
        reasons.append(f"frequent recurrence ({max(recurrence, frequency):.0f}/100)")
    if recency >= 60:
        reasons.append(f"very recent occurrence ({recency:.0f}/100)")

    environment = str(_field(event, "environment", "production")).lower()
    if environment == "production":
        reasons.append("production impact")

    driver = ", ".join(reasons) if reasons else "its composite weighted score"
    rank = int(_num(ranking_data, "rank") or 0)
    return (
        f"Ranked #{rank} by the scoring engine due to {driver} "
        f"(priority score {_headline_score(ranking_data):.0f}/100)."
    )


def _template_structured(event: Any, ranking_data: Dict[str, Any]) -> Dict[str, str]:
    """Deterministic fallback in the exact contract shape (provider=fallback)."""
    category = _incident_category(event)
    severity = str(_field(event, "severity", "unknown")).upper()
    service = str(_field(event, "service", "unknown-service"))
    region = str(_field(event, "region", "global"))
    environment = str(_field(event, "environment", "production"))
    etype_human = str(_field(event, "event_type", "issue")).replace("_", " ").strip()
    title = str(_field(event, "title", "")).strip()
    headline = title or etype_human

    location = f"{environment} ({region})" if environment != "production" else region

    labels = {
        "deployment": "deployment-related incident",
        "infrastructure": "infrastructure incident",
        "security": "security incident",
        "application_error": "application incident",
        "generic": "operational event",
    }
    summary = (
        f"{severity}: {labels[category]} detected on '{service}' "
        f"in {location}: {headline}."
    )

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
    """Legacy adapter matching the existing triage-router stub signature.

    Returns ``(explanation_text, suggested_action)`` where the explanation text
    combines summary and why-prioritized reasoning. Thin wrapper over
    :func:`generate_explanation`; same guarantees apply.
    """
    return _to_pair(await generate_explanation(event, ranking_data))
