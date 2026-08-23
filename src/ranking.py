from datetime import datetime, timezone
from typing import Dict, List, Any


DEFAULT_WEIGHTS = {
    "severity": 0.30,
    "business_impact": 0.15,
    "anomaly": 0.20,
    "frequency": 0.20,
    "recency": 0.15,
}

SEVERITY_MAP = {
    "critical": 1.00,
    "high": 0.75,
    "medium": 0.50,
    "low": 0.25,
    "info": 0.10,
}


def calculate_severity_score(severity: str) -> float:
    """Convert severity into a normalized 0-1 score."""
    return SEVERITY_MAP.get(str(severity).lower(), 0.0)


def calculate_business_impact_score(event: Dict[str, Any]) -> float:
    """Estimate business impact from environment, region and service."""
    raw = event.get("raw_payload") or {}

    if "business_impact" in raw:
        try:
            return max(0.0, min(float(raw["business_impact"]), 1.0))
        except (TypeError, ValueError):
            pass

    score = 0.0

    if str(event.get("environment", "")).lower() == "production":
        score += 0.35

    if str(event.get("region", "")).lower() == "global":
        score += 0.30

    service = str(event.get("service", "")).lower()

    high_impact_services = [
        "payment",
        "database",
        "auth",
        "gateway",
        "checkout",
    ]

    if any(keyword in service for keyword in high_impact_services):
        score += 0.35

    return min(score, 1.0)


def calculate_anomaly_score(event: Dict[str, Any]) -> float:
    """Deterministic rule-based anomaly score."""
    score = 0.0

    text = (
        str(event.get("title", ""))
        + " "
        + str(event.get("description", ""))
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


def calculate_frequency_score(
    event: Dict[str, Any],
    all_events: List[Dict[str, Any]],
) -> float:
    """Score repeated occurrences of the same event type and service."""
    event_type = event.get("event_type")
    service = event.get("service")

    count = sum(
        1
        for other in all_events
        if other.get("event_type") == event_type
        and other.get("service") == service
    )

    return min(count / 5.0, 1.0)


def calculate_recency_score(event: Dict[str, Any]) -> float:
    """
    Recent events receive a higher score.
    Uses event timestamp when available.
    """
    timestamp = event.get("timestamp")

    if not timestamp:
        return 0.5

    try:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_seconds = max((now - timestamp).total_seconds(), 0)

        # 0 minutes old -> 1.0
        # 30 minutes old -> 0.5
        # 60+ minutes old -> 0.0
        score = max(0.0, 1.0 - age_seconds / 3600.0)

        return round(score, 3)

    except (TypeError, ValueError):
        return 0.5


def calculate_priority_score(
    severity_score: float,
    business_impact_score: float,
    anomaly_score: float,
    frequency_score: float,
    recency_score: float,
    weights: Dict[str, float],
) -> float:
    """Calculate final normalized priority score from 0.0 to 1.0."""
    return round(
        severity_score * weights["severity"]
        + business_impact_score * weights["business_impact"]
        + anomaly_score * weights["anomaly"]
        + frequency_score * weights["frequency"]
        + recency_score * weights["recency"],
        3,
    )


def rank_events(
    events: List[Dict[str, Any]],
    weights: Dict[str, float] | None = None,
) -> List[Dict[str, Any]]:
    """Calculate five-factor scores and rank events."""
    weights = weights or DEFAULT_WEIGHTS.copy()

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
        severity = calculate_severity_score(
            event.get("severity", "medium")
        )

        business_impact = calculate_business_impact_score(event)

        anomaly = calculate_anomaly_score(event)

        frequency = calculate_frequency_score(
            event,
            events,
        )

        recency = calculate_recency_score(event)

        priority = calculate_priority_score(
            severity,
            business_impact,
            anomaly,
            frequency,
            recency,
            weights,
        )

        ranked.append(
            {
                "event_id": event.get("id"),
                "rank": 0,
                "score": priority,
                "priority_score": priority,
                "severity_score": round(severity, 3),
                "business_impact_score": round(business_impact, 3),
                "anomaly_score": round(anomaly, 3),
                "frequency_score": round(frequency, 3),
                "recency_score": round(recency, 3),
                "status": "open",
                "event": event,
            }
        )

    ranked.sort(
        key=lambda item: item["priority_score"],
        reverse=True,
    )

    for index, item in enumerate(ranked, start=1):
        item["rank"] = index

    return ranked


def adjust_weights(
    current_weights: Dict[str, float],
    feedback: Dict[str, float],
) -> Dict[str, float]:
    """
    Update ranking weights using operator feedback.

    Supported keys:
    severity_weight
    business_impact_weight
    anomaly_weight
    frequency_weight
    recency_weight
    """
    updated = current_weights.copy()

    mapping = {
        "severity_weight": "severity",
        "business_impact_weight": "business_impact",
        "anomaly_weight": "anomaly",
        "frequency_weight": "frequency",
        "recency_weight": "recency",
    }

    for feedback_key, weight_key in mapping.items():
        if feedback_key in feedback:
            updated[weight_key] = float(feedback[feedback_key])

    updated = {
        key: max(0.0, min(float(value), 1.0))
        for key, value in updated.items()
    }

    total = sum(updated.values())

    if total <= 0:
        return DEFAULT_WEIGHTS.copy()

    return {
        key: round(value / total, 4)
        for key, value in updated.items()
    }