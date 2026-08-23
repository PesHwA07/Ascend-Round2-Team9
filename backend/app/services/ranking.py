from typing import List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import math

from backend.app.models import Event, WeightConfig
from backend.app.config import settings

TIER_1_SERVICES = {"payment-api", "gateway", "auth-service", "auth-gateway", "cart-checkout", "order-db", "stripe-connector"}

def get_current_weights(db: Session) -> Dict[str, float]:
    """Retrieve the latest active 5-signal ranking weights from DB or settings."""
    config = db.query(WeightConfig).order_by(WeightConfig.id.desc()).first()
    if config:
        return {
            "severity": config.severity,
            "frequency": config.frequency,
            "recency": config.recency,
            "anomaly": config.anomaly,
            "business_impact": config.business_impact
        }
    return dict(settings.DEFAULT_WEIGHTS)

def update_weights(
    db: Session,
    severity: float = None,
    frequency: float = None,
    recency: float = None,
    anomaly: float = None,
    business_impact: float = None,
    actor: str = "operator"
) -> WeightConfig:
    """Update or create a new active 5-weight configuration record."""
    current = get_current_weights(db)
    
    new_sev = severity if severity is not None else current["severity"]
    new_freq = frequency if frequency is not None else current["frequency"]
    new_rec = recency if recency is not None else current["recency"]
    new_anom = anomaly if anomaly is not None else current["anomaly"]
    new_biz = business_impact if business_impact is not None else current["business_impact"]

    # Normalize weights so sum is 1.0
    total = new_sev + new_freq + new_rec + new_anom + new_biz
    if total > 0:
        new_sev = round(new_sev / total, 4)
        new_freq = round(new_freq / total, 4)
        new_rec = round(new_rec / total, 4)
        new_anom = round(new_anom / total, 4)
        new_biz = round(new_biz / total, 4)

    config = WeightConfig(
        severity=new_sev,
        frequency=new_freq,
        recency=new_rec,
        anomaly=new_anom,
        business_impact=new_biz,
        updated_by=actor,
        updated_at=datetime.now(timezone.utc)
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config

def calculate_severity_component(severity: str) -> float:
    """Normalized 0.0 - 1.0 severity score."""
    mapping = {
        "critical": 1.0,
        "warning": 0.75,
        "high": 0.75,
        "medium": 0.50,
        "low": 0.25,
        "info": 0.10
    }
    return mapping.get(str(severity).lower(), 0.50)

def calculate_frequency_component(event: Event, event_batch: List[Event]) -> float:
    """Normalized frequency/recurrence score based on matching service & error type."""
    if not event_batch:
        return 0.20
    matches = sum(
        1 for e in event_batch
        if e.service == event.service and e.id != event.id
    )
    return min(1.0, 0.20 + (matches * 0.15))

def calculate_recency_component(event: Event) -> float:
    """Time-decay score (recent events within 60s get ~1.0)."""
    now = datetime.now(timezone.utc)
    evt_time = event.timestamp
    if evt_time.tzinfo is None:
        evt_time = evt_time.replace(tzinfo=timezone.utc)
        
    diff_sec = max(0, (now - evt_time).total_seconds())
    # Exponential time decay over 1 hour
    decay = math.exp(-diff_sec / 1800.0)
    return round(max(0.10, min(1.0, decay)), 2)

def calculate_anomaly_component(event: Event) -> float:
    """Anomaly deviation score parsed from details payload (0.0 - 1.0)."""
    details = event.details or {}
    score = 0.30
    
    # 1. Error rate %
    if "error_rate_percent" in details or "error_rate_pct" in details:
        try:
            rate = float(details.get("error_rate_percent") or details.get("error_rate_pct") or 0)
            score += min(0.60, rate / 50.0)
        except (ValueError, TypeError):
            pass
            
    # 2. Metric threshold breach (e.g. CPU, RAM)
    if "metric_value" in details and "threshold" in details:
        try:
            val = float(details["metric_value"])
            thresh = float(details["threshold"])
            if val > thresh:
                score += min(0.60, ((val - thresh) / thresh) + 0.30)
        except (ValueError, TypeError):
            pass

    # 3. Z-score deviation
    if "z_score" in details or "deviation" in details:
        try:
            z = abs(float(details.get("z_score") or details.get("deviation") or 0))
            score += min(0.60, z * 0.20)
        except (ValueError, TypeError):
            pass

    # 4. Failed attempts / Restarts
    if "failed_attempts" in details or "container_restarts" in details:
        try:
            restarts = float(details.get("failed_attempts") or details.get("container_restarts") or 0)
            score += min(0.50, restarts * 0.10)
        except (ValueError, TypeError):
            pass

    return round(min(1.0, max(0.10, score)), 2)

def calculate_business_impact_component(event: Event) -> float:
    """Business impact score (Tier 1 core services get higher score)."""
    if event.service in TIER_1_SERVICES or "payment" in event.service.lower() or "gateway" in event.service.lower():
        return 1.0
    if event.environment == "production":
        return 0.80
    return 0.40

def rank_events(events: List[Event], weights: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Score and rank a list of events using the 5-signal weighted scoring system.
    Returns sorted list with score_breakdown, rank, and final score (0.0 to 1.0).
    """
    scored_items = []
    
    w_sev = weights.get("severity", 0.30)
    w_freq = weights.get("frequency", 0.20)
    w_rec = weights.get("recency", 0.15)
    w_anom = weights.get("anomaly", 0.20)
    w_biz = weights.get("business_impact", 0.15)
    
    for event in events:
        s_sev = calculate_severity_component(event.severity)
        s_freq = calculate_frequency_component(event, events)
        s_rec = calculate_recency_component(event)
        s_anom = calculate_anomaly_component(event)
        s_biz = calculate_business_impact_component(event)
        
        breakdown = {
            "severity": round(s_sev * w_sev, 3),
            "frequency": round(s_freq * w_freq, 3),
            "recency": round(s_rec * w_rec, 3),
            "anomaly": round(s_anom * w_anom, 3),
            "business_impact": round(s_biz * w_biz, 3)
        }
        
        final_score = round(sum(breakdown.values()), 3)
        
        scored_items.append({
            "event": event,
            "score": final_score,
            "priority_score": final_score,
            "score_breakdown": breakdown
        })
        
    # Sort descending by priority score
    scored_items.sort(key=lambda x: x["score"], reverse=True)
    
    # Assign 1-indexed ranks
    for idx, item in enumerate(scored_items, start=1):
        item["rank"] = idx
        
    return scored_items

def adjust_weights(
    current_weights: Dict[str, float],
    feedback: Dict[str, float],
) -> Dict[str, float]:
    """
    Apply operator feedback to the five ranking weights.

    The returned weights are normalized so their total is 1.0.

    Supported feedback keys:
        severity_weight
        frequency_weight
        recency_weight
        anomaly_weight
        business_impact_weight
    """
    updated = current_weights.copy()

    mapping = {
        "severity_weight": "severity",
        "frequency_weight": "frequency",
        "recency_weight": "recency",
        "anomaly_weight": "anomaly",
        "business_impact_weight": "business_impact",
    }

    for feedback_key, weight_key in mapping.items():
        if feedback_key in feedback:
            try:
                updated[weight_key] = float(feedback[feedback_key])
            except (TypeError, ValueError):
                continue

    # Keep every weight within the valid 0-1 range.
    updated = {
        key: max(0.0, min(float(value), 1.0))
        for key, value in updated.items()
    }

    total = sum(updated.values())

    # Prevent an invalid all-zero configuration.
    if total <= 0:
        return {
            "severity": 0.30,
            "frequency": 0.20,
            "recency": 0.15,
            "anomaly": 0.20,
            "business_impact": 0.15,
        }

    return {
        key: round(value / total, 4)
        for key, value in updated.items()
    }
