from typing import List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import math

from backend.app.models import Event, WeightConfig
from backend.app.config import settings

def get_current_weights(db: Session) -> Dict[str, float]:
    """Retrieve the latest active ranking weights from the database or default settings."""
    config = db.query(WeightConfig).order_by(WeightConfig.id.desc()).first()
    if config:
        return {
            "severity_weight": config.severity_weight,
            "blast_radius_weight": config.blast_radius_weight,
            "anomaly_weight": config.anomaly_weight,
            "recurrence_weight": config.recurrence_weight
        }
    return {
        "severity_weight": settings.DEFAULT_SEVERITY_WEIGHT,
        "blast_radius_weight": settings.DEFAULT_BLAST_RADIUS_WEIGHT,
        "anomaly_weight": settings.DEFAULT_ANOMALY_WEIGHT,
        "recurrence_weight": settings.DEFAULT_RECURRENCE_WEIGHT
    }

def update_weights(
    db: Session,
    severity_weight: float = None,
    blast_radius_weight: float = None,
    anomaly_weight: float = None,
    recurrence_weight: float = None,
    actor: str = "operator"
) -> WeightConfig:
    """Update or create a new active weight configuration record."""
    current = get_current_weights(db)
    
    new_w_sev = severity_weight if severity_weight is not None else current["severity_weight"]
    new_w_blast = blast_radius_weight if blast_radius_weight is not None else current["blast_radius_weight"]
    new_w_anom = anomaly_weight if anomaly_weight is not None else current["anomaly_weight"]
    new_w_rec = recurrence_weight if recurrence_weight is not None else current["recurrence_weight"]

    # Normalize weights so sum is 1.0 if greater than 0
    total = new_w_sev + new_w_blast + new_w_anom + new_w_rec
    if total > 0:
        new_w_sev = round(new_w_sev / total, 4)
        new_w_blast = round(new_w_blast / total, 4)
        new_w_anom = round(new_w_anom / total, 4)
        new_w_rec = round(new_w_rec / total, 4)

    config = WeightConfig(
        severity_weight=new_w_sev,
        blast_radius_weight=new_w_blast,
        anomaly_weight=new_w_anom,
        recurrence_weight=new_w_rec,
        updated_by=actor,
        updated_at=datetime.now(timezone.utc)
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config

def calculate_severity_score(severity: str) -> float:
    """Map standard severity strings to 0-100 score."""
    mapping = {
        "critical": 100.0,
        "high": 75.0,
        "medium": 50.0,
        "low": 25.0,
        "info": 10.0
    }
    return mapping.get(str(severity).lower(), 50.0)

def calculate_blast_radius_score(event: Event) -> float:
    """Calculate blast radius based on environment, region, and payload signals."""
    score = 40.0
    
    if event.environment == "production":
        score += 30.0
    elif event.environment == "staging":
        score += 10.0
        
    if event.region == "global" or "global" in str(event.region).lower():
        score += 20.0
    elif "multi" in str(event.region).lower():
        score += 15.0
        
    payload = event.raw_payload or {}
    affected_users = payload.get("affected_users") or payload.get("users_impacted") or 0
    if affected_users:
        try:
            val = float(affected_users)
            score += min(10.0, math.log10(val + 1) * 2.5)
        except (ValueError, TypeError):
            pass

    return min(100.0, max(0.0, score))

def calculate_anomaly_score(event: Event) -> float:
    """Calculate anomaly deviation score from event payload metrics."""
    payload = event.raw_payload or {}
    score = 30.0

    # Check for deviation metrics
    if "deviation" in payload or "z_score" in payload:
        try:
            z = abs(float(payload.get("z_score") or payload.get("deviation") or 0))
            score += min(50.0, z * 15.0)
        except (ValueError, TypeError):
            pass
            
    # Check for error rates or latency spike
    if "error_rate_pct" in payload:
        try:
            rate = float(payload.get("error_rate_pct", 0))
            score += min(40.0, rate * 0.8)
        except (ValueError, TypeError):
            pass

    if "latency_p99_ms" in payload:
        try:
            latency = float(payload.get("latency_p99_ms", 0))
            if latency > 1000:
                score += min(30.0, (latency / 500) * 5)
        except (ValueError, TypeError):
            pass

    if "failed_attempts" in payload:
        try:
            fails = float(payload.get("failed_attempts", 0))
            score += min(40.0, fails * 2.0)
        except (ValueError, TypeError):
            pass

    return min(100.0, max(0.0, score))

def calculate_recurrence_score(event: Event, event_history: List[Event]) -> float:
    """Calculate frequency/recurrence score based on recent matching events."""
    if not event_history:
        return 20.0
        
    # Count occurrences of same service + event_type in the recent history batch
    matches = sum(
        1 for e in event_history
        if e.service == event.service and e.event_type == event.event_type and e.id != event.id
    )
    
    score = 20.0 + min(80.0, matches * 15.0)
    return min(100.0, score)

def rank_events(events: List[Event], weights: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Score and rank a list of events using weighted scoring.
    Returns sorted list of dictionaries with scores and rank.
    """
    scored_items = []
    
    w_sev = weights.get("severity_weight", 0.35)
    w_blast = weights.get("blast_radius_weight", 0.25)
    w_anom = weights.get("anomaly_weight", 0.20)
    w_rec = weights.get("recurrence_weight", 0.20)
    
    for event in events:
        s_sev = calculate_severity_score(event.severity)
        s_blast = calculate_blast_radius_score(event)
        s_anom = calculate_anomaly_score(event)
        s_rec = calculate_recurrence_score(event, events)
        
        priority_score = round(
            (s_sev * w_sev) +
            (s_blast * w_blast) +
            (s_anom * w_anom) +
            (s_rec * w_rec),
            2
        )
        
        scored_items.append({
            "event": event,
            "priority_score": priority_score,
            "severity_score": round(s_sev, 2),
            "blast_radius_score": round(s_blast, 2),
            "anomaly_score": round(s_anom, 2),
            "recurrence_score": round(s_rec, 2)
        })
        
    # Sort descending by priority score
    scored_items.sort(key=lambda x: x["priority_score"], reverse=True)
    
    # Assign ranks (1-indexed)
    for idx, item in enumerate(scored_items, start=1):
        item["rank"] = idx
        
    return scored_items
