import logging
from typing import Dict, Any, Tuple
import os

from backend.app.models import Event
from backend.app.config import settings

logger = logging.getLogger("aurabrief.explainer")

def generate_template_explanation(event: Event, score_data: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Fast, deterministic template explanation generator (sub-millisecond SLA guarantee).
    Returns (explanation, explanation_type, suggested_action).
    """
    sev = event.severity.upper()
    svc = event.service
    region = event.region
    details = event.details or {}
    score = score_data.get("score", score_data.get("priority_score", 0.0))
    
    # Context-aware explanation text
    if event.source == "infra-monitor":
        metric = details.get("metric_name", "system metric").replace("_", " ")
        val = details.get("metric_value", "high")
        thresh = details.get("threshold", "limit")
        explanation = (
            f"{sev} alert on '{svc}' ({region}): {metric} reached {val} exceeding threshold {thresh}. "
            f"Overall triage priority score is {score:.2f}/1.0."
        )
        action = f"Check pod/node autoscaling and inspect recent resource consumption on '{svc}'."
    elif event.source == "deploy-events":
        dtype = details.get("deploy_type", "deployment").replace("_", " ")
        ver_to = details.get("version_to", "latest")
        reason = details.get("failure_reason") or "Health check failure"
        explanation = (
            f"{sev} deployment incident on '{svc}' ({region}): {dtype} for {ver_to}. "
            f"Reason: {reason}. Priority score: {score:.2f}/1.0."
        )
        action = f"Initiate immediate rollback of '{svc}' and monitor error rate stabilization."
    elif event.source == "app-errors":
        etype = details.get("error_type", "Application error").replace("_", " ")
        rate = details.get("error_rate_percent", "elevated")
        explanation = (
            f"{sev} application error on '{svc}' ({region}): {etype} with {rate}% error rate. "
            f"Priority score: {score:.2f}/1.0. {event.title}"
        )
        action = f"Investigate downstream database/gateway connections and check exception logs for '{svc}'."
    else:
        explanation = (
            f"{sev} incident on '{svc}' in {region}. Priority score: {score:.2f}/1.0. "
            f"{event.title}."
        )
        action = f"Triage logs for service '{svc}' and notify the on-call engineer."
        
    return explanation, "template", action

async def generate_explanation(event: Event, score_data: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Generate explanation and suggested action for an event.
    Attempts Gemini or Ollama if available, falls back to template generator with explanation_type='template'.
    """
    # 1. Try Google Gemini API if key is present
    if settings.GEMINI_API_KEY:
        try:
            import httpx
            prompt = (
                f"You are an AI SRE ops brief assistant. Provide a 2-sentence executive summary and 1-sentence recommended action for:\n"
                f"Service: {event.service}, Severity: {event.severity}, Region: {event.region}, Source: {event.source}\n"
                f"Title: {event.title}, Details: {event.details}, Score: {score_data.get('score', 0)}\n"
                f"Format EXACTLY as:\nExplanation: <text>\nAction: <text>"
            )
            async with httpx.AsyncClient(timeout=1.5) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
                resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    lines = text.split("\n")
                    exp = lines[0].replace("Explanation:", "").strip()
                    act = lines[1].replace("Action:", "").strip() if len(lines) > 1 else "Investigate service logs."
                    return exp, "ai", act
        except Exception as e:
            logger.warning(f"Gemini API generation failed/timed out: {e}")

    # 2. Try Local Ollama if configured
    if settings.OLLAMA_HOST and settings.OLLAMA_HOST != "http://host.docker.internal:11434":
        try:
            import httpx
            prompt = f"Brief 2-sentence SRE summary and action for {event.severity} incident on {event.service}: {event.title}"
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.post(f"{settings.OLLAMA_HOST}/api/generate", json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                })
                if resp.status_code == 200:
                    res_text = resp.json().get("response", "").strip()
                    return res_text, "ai", "Review telemetry and alert on-call engineer."
        except Exception as e:
            logger.warning(f"Ollama generation failed/timed out: {e}")

    # 3. Default fast deterministic fallback
    return generate_template_explanation(event, score_data)
