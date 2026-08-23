from datetime import datetime, timezone
from typing import Dict, List, Any


# Default weights — total = 1.0
DEFAULT_WEIGHTS = {
    "severity": 0.30,
    "blast_radius": 0.25,
    "anomaly": 0.25,
    "recurrence": 0.20,
}

SEVERITY_MAP = {
    "critical": 1.00,
    "high": 0.75,
    "medium": 0.50,
    "low": 0.25,
    "info": 0.10,
}


def calculate_severity_score(severity: str) -> float:
    """Convert severity level to a normalized 0-1 score."""
    return SEVERITY_MAP.get(str(severity).lower(), 0.0)


def calculate_blast_radius_score(event: Dict[str, Any]) -> float:
    """
    Estimate impact based on affected service/environment/region.
    Uses raw_payload values when available.
    """

    raw = event.get("raw_payload") or {}

    # If simulator/API provides an explicit blast radius, use it.
    if "blast_radius" in raw:
        try:
            return max(0.0, min(float(raw["blast_radius"]), 1.0))
        except (TypeError, ValueError):
            pass

    score = 0.0

    # Production systems are more important.
    if str(event.get("environment", "")).lower() == "production":
        score += 0.35

    # Global region suggests wider impact.
    if str(event.get("region", "")).lower() == "global":
        score += 0.30

    # Common high-impact service keywords.
    service = str(event.get("service", "")).lower()
    high_impact_services = [
        "payment",
        "database",
        "auth",
        "gateway",
        "checkout",
    ]

    if any(x in service for x in high_impact_services):
        score += 0.35

    return min(score, 1.0)


def calculate_anomaly_score(event: Dict[str, Any]) -> float:
    """
    Rule-based anomaly detection.
    No LLM/ML is used, making the result deterministic.
    """

    score = 0.0

    text = (
        str(event.get("title", "")) + " " +
        str(event.get("description", ""))
    ).lower()

    anomaly_keywords = [
        "failure",
        "failed",
        "down",
        "timeout",
        "unavailable",
        "error",
        "attack",
        "breach",
        "crash",
        "spike",
        "burst",
        "abnormal",
    ]

    matches = sum(1 for word in anomaly_keywords if word in text)

    score += min(matches * 0.15, 0.45)

    severity = str(event.get("severity", "")).lower()

    if severity == "critical":
        score += 0.35
    elif severity == "high":
        score += 0.25

    raw = event.get("raw_payload") or {}

    # Optional telemetry-based anomaly indicators.
    if raw.get("error_rate") is not None:
        try:
            error_rate = float(raw["error_rate"])
            if error_rate >= 0.20:
                score += 0.25
            elif error_rate >= 0.10:
                score += 0.15
        except (TypeError, ValueError):
            pass

    return min(score, 1.0)


def calculate_recurrence_score(
    event: Dict[str, Any],
    all_events: List[Dict[str, Any]],
) -> float:
    """
    Calculate how frequently similar events occur.
    Similarity is based on event_type + service.
    """

    event_type = event.get("event_type")
    service = event.get("service")

    count = sum(
        1
        for other in all_events
        if other.get("event_type") == event_type
        and other.get("service") == service
    )

    # 5 or more repeated events reaches maximum recurrence score.
    return min(count / 5.0, 1.0)


def calculate_priority_score(
    severity_score: float,
    blast_radius_score: float,
    anomaly_score: float,
    recurrence_score: float,
    weights: Dict[str, float],
) -> float:
    """Calculate final priority score from 0-100."""

    score = (
        severity_score * weights["severity"]
        + blast_radius_score * weights["blast_radius"]
        + anomaly_score * weights["anomaly"]
        + recurrence_score * weights["recurrence"]
    )

    return round(score * 100, 2)


def get_priority(score: float) -> str:
    """Convert score into priority label."""

    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"

    return "low"


def rank_events(
    events: List[Dict[str, Any]],
    weights: Dict[str, float] | None = None,
) -> List[Dict[str, Any]]:
    """
    Main ranking engine.

    Takes incoming events and returns ranked triage items.
    """

    weights = weights or DEFAULT_WEIGHTS.copy()

    # Normalize weights to guarantee deterministic total = 1.
    total = sum(weights.values())

    if total <= 0:
        weights = DEFAULT_WEIGHTS.copy()
    else:
        weights = {
            key: value / total
            for key, value in weights.items()
        }

    ranked = []

    for event in events:
        severity_score = calculate_severity_score(
            event.get("severity", "medium")
        )

        blast_radius_score = calculate_blast_radius_score(event)

        anomaly_score = calculate_anomaly_score(event)

        recurrence_score = calculate_recurrence_score(
            event,
            events,
        )

        priority_score = calculate_priority_score(
            severity_score,
            blast_radius_score,
            anomaly_score,
            recurrence_score,
            weights,
        )

        ranked.append({
            "event_id": event.get("id"),
            "rank": 0,
            "priority_score": priority_score,
            "severity_score": round(severity_score, 3),
            "blast_radius_score": round(blast_radius_score, 3),
            "anomaly_score": round(anomaly_score, 3),
            "recurrence_score": round(recurrence_score, 3),
            "status": "open",
            "event": event,
        })

    # Highest score first.
    ranked.sort(
        key=lambda item: item["priority_score"],
        reverse=True,
    )

    # Assign rank after sorting.
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index

    return ranked


def adjust_weights(
    current_weights: Dict[str, float],
    feedback: Dict[str, float],
) -> Dict[str, float]:
    """
    Feedback loop.

    Example:
    {
        "severity_weight": 0.35,
        "anomaly_weight": 0.30
    }
    """

    updated = current_weights.copy()

    mapping = {
        "severity_weight": "severity",
        "blast_radius_weight": "blast_radius",
        "anomaly_weight": "anomaly",
        "recurrence_weight": "recurrence",
    }

    for feedback_key, weight_key in mapping.items():
        if feedback_key in feedback:
            updated[weight_key] = float(feedback[feedback_key])

    # Keep weights valid and deterministic.
    updated = {
        key: max(0.0, min(float(value), 1.0))
        for key, value in updated.items()
    }

    total = sum(updated.values())

    if total == 0:
        return DEFAULT_WEIGHTS.copy()

    return {
        key: round(value / total, 4)
        for key, value in updated.items()
    }