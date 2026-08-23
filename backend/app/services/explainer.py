import logging
from typing import Dict, Any, Tuple, Optional
import os

from backend.app.models import Event
from backend.app.config import settings

logger = logging.getLogger("aurabrief.explainer")

PROVIDER_OLLAMA = "ollama"
PROVIDER_GEMINI = "gemini"
PROVIDER_FALLBACK = "fallback"

def generate_template_explanation(event: Event, score_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Fast, deterministic template explanation generator (sub-millisecond SLA guarantee).
    Returns dictionary with summary, why_prioritized, recommended_action, provider.
    """
    sev = event.severity.upper()
    svc = event.service
    region = event.region
    details = event.details or {}
    score = score_data.get("score", score_data.get("priority_score", 0.0))
    rank = score_data.get("rank", 1)
    
    # 1. Summary
    if event.source == "infra-monitor":
        metric = details.get("metric_name", "system metric").replace("_", " ")
        val = details.get("metric_value", "high")
        thresh = details.get("threshold", "limit")
        summary = f"{sev} infrastructure alert on '{svc}' ({region}): {metric} reached {val} exceeding threshold {thresh}."
        action = f"Check pod/node autoscaling and inspect recent resource consumption on '{svc}'."
    elif event.source == "deploy-events":
        dtype = details.get("deploy_type", "deployment").replace("_", " ")
        ver_to = details.get("version_to", "latest")
        reason = details.get("failure_reason") or "Health check timeout"
        summary = f"{sev} deployment incident on '{svc}' ({region}): {dtype} for {ver_to} (Reason: {reason})."
        action = f"Initiate immediate rollback of '{svc}' and monitor error rate stabilization."
    elif event.source == "app-errors":
        etype = details.get("error_type", "Application error").replace("_", " ")
        rate = details.get("error_rate_percent", "elevated")
        summary = f"{sev} application error on '{svc}' ({region}): {etype} with {rate}% error rate."
        action = f"Investigate downstream database/gateway connections and check exception logs for '{svc}'."
    else:
        summary = f"{sev} incident on '{svc}' in {region}: {event.title}."
        action = f"Triage logs for service '{svc}' and notify the on-call engineer."

    # 2. Why Prioritized
    why_prioritized = f"Ranked #{rank} with priority score {score:.2f}/1.0 based on severity and anomalous metric deviations."

    return {
        "summary": summary,
        "why_prioritized": why_prioritized,
        "recommended_action": action,
        "provider": PROVIDER_FALLBACK
    }

async def generate_explanation(event: Event, score_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate structured explanation for an event.
    Returns Dict with summary, why_prioritized, recommended_action, and provider.
    """
    # 1. Try Local Ollama via OLLAMA_HOST
    ollama_host = os.getenv("OLLAMA_HOST", getattr(settings, "OLLAMA_HOST", "http://host.docker.internal:11434"))
    ollama_model = os.getenv("OLLAMA_MODEL", getattr(settings, "OLLAMA_MODEL", "llama3"))

    if ollama_host and ollama_host != "http://host.docker.internal:11434":
        try:
            import httpx
            prompt = (
                f"You are an AI SRE ops brief assistant. Provide 3 short lines:\n"
                f"SUMMARY: <what happened on {event.service}>\n"
                f"WHY: <why it is prioritized with score {score_data.get('score', 0)}>\n"
                f"ACTION: <remediation step for {event.service}>\n"
                f"Event: {event.severity} on {event.service} ({event.region}) - {event.title}."
            )
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.post(f"{ollama_host}/api/generate", json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False
                })
                if resp.status_code == 200:
                    raw_text = resp.json().get("response", "").strip()
                    lines = [l for l in raw_text.split("\n") if ":" in l]
                    summary = lines[0].split(":", 1)[1].strip() if len(lines) > 0 else f"{event.severity.upper()} incident on {event.service}."
                    why = lines[1].split(":", 1)[1].strip() if len(lines) > 1 else f"Ranked #{score_data.get('rank', 1)} by priority score."
                    action = lines[2].split(":", 1)[1].strip() if len(lines) > 2 else "Review service logs and on-call runbook."
                    return {
                        "summary": summary,
                        "why_prioritized": why,
                        "recommended_action": action,
                        "provider": PROVIDER_OLLAMA
                    }
        except Exception as e:
            logger.warning(f"Ollama generation failed/timed out: {e}")

    # 2. Try Google Gemini API if key is present
    if settings.GEMINI_API_KEY:
        try:
            import httpx
            prompt = (
                f"You are an AI SRE ops brief assistant. Provide 3 short lines:\n"
                f"SUMMARY: <what happened>\n"
                f"WHY: <why prioritized score {score_data.get('score', 0)}>\n"
                f"ACTION: <action step>\n"
                f"Service: {event.service}, Severity: {event.severity}, Region: {event.region}, Source: {event.source}\n"
                f"Title: {event.title}, Details: {event.details}"
            )
            async with httpx.AsyncClient(timeout=1.5) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
                resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    lines = [l for l in text.split("\n") if ":" in l]
                    summary = lines[0].split(":", 1)[1].strip() if len(lines) > 0 else f"{event.severity.upper()} incident on {event.service}."
                    why = lines[1].split(":", 1)[1].strip() if len(lines) > 1 else f"Ranked #{score_data.get('rank', 1)} by priority score."
                    action = lines[2].split(":", 1)[1].strip() if len(lines) > 2 else "Investigate service telemetry."
                    return {
                        "summary": summary,
                        "why_prioritized": why,
                        "recommended_action": action,
                        "provider": PROVIDER_GEMINI
                    }
        except Exception as e:
            logger.warning(f"Gemini API generation failed/timed out: {e}")

    # 3. Default fast deterministic fallback
    return generate_template_explanation(event, score_data)
