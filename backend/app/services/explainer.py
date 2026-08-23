import logging
from typing import Dict, Any, Tuple
from backend.app.models import Event
from backend.app.config import settings

logger = logging.getLogger("aurabrief.explainer")

def generate_template_explanation(event: Event, score_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Fast, reliable deterministic explanation generator (sub-millisecond SLA guarantee).
    Returns (explanation, suggested_action).
    """
    sev = event.severity.upper()
    svc = event.service
    etype = event.event_type.replace("_", " ").title()
    region = event.region
    env = event.environment
    p_score = score_data.get("priority_score", 0.0)
    
    explanation = (
        f"{sev} priority incident ({etype}) detected on '{svc}' in {env} ({region}). "
        f"Overall priority score is {p_score}/100 driven by high severity and anomalous metrics. "
        f"{event.description}"
    ).strip()
    
    # Context-aware suggested actions
    if "cpu" in event.event_type.lower() or "memory" in event.event_type.lower():
        action = f"Check pod/instance autoscaling metrics for '{svc}' and inspect recent deployment changes or resource leaks."
    elif "auth" in event.event_type.lower() or "login" in event.event_type.lower() or "security" in event.stream_source:
        action = f"Review security logs for IP blocklist triggers, rotate active API tokens if compromised, and verify WAF rate limits."
    elif "latency" in event.event_type.lower() or "payment" in event.event_type.lower() or "db" in event.event_type.lower():
        action = f"Investigate downstream database connection pool and check gateway timeout configurations for '{svc}'."
    elif "deploy" in event.event_type.lower() or "crash" in event.event_type.lower():
        action = f"Initiate immediate rollback of the last release for '{svc}' and monitor error rate stabilization."
    else:
        action = f"Triage '{svc}' service logs, check health endpoints in {region}, and alert on-call engineer."
        
    return explanation, action

async def generate_explanation(event: Event, score_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Generate explanation and suggested action for an event.
    Falls back gracefully to template-based generator to maintain sub-5s SLA.
    """
    # If Gemini API key is configured, integration hook for Gen-AI lead
    if settings.GEMINI_API_KEY:
        try:
            import httpx
            prompt = (
                f"You are an AI SRE ops assistant. Provide a 2-sentence incident explanation and a 1-sentence recommended action for:\n"
                f"Service: {event.service}\nSeverity: {event.severity}\nType: {event.event_type}\n"
                f"Title: {event.title}\nDescription: {event.description}\nPayload: {event.raw_payload}\n"
                f"Priority Score: {score_data.get('priority_score')}/100\n"
                f"Format as: Explanation: <text>\nAction: <text>"
            )
            # Fast timeout to guarantee response time
            async with httpx.AsyncClient(timeout=1.5) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
                response = await client.post(url, json={
                    "contents": [{"parts": [{"text": prompt}]}]
                })
                if response.status_code == 200:
                    data = response.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    lines = text.split("\n")
                    exp = lines[0].replace("Explanation:", "").strip()
                    act = lines[1].replace("Action:", "").strip() if len(lines) > 1 else "Investigate logs and alert on-call."
                    return exp, act
        except Exception as e:
            logger.warning(f"Gen-AI call failed/timed out, falling back to template: {e}")

    # Default robust fallback
    return generate_template_explanation(event, score_data)
