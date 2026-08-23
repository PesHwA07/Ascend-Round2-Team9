from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import time
import uuid
from typing import Optional

from backend.app.database import get_db
from backend.app.models import Event, TriageSnapshot, TriageItem
from backend.app.schemas import (
    TriageCurrentResponse,
    TriageHistoryResponse,
    TriageSnapshotSummary,
    TriageItemResponse,
    EventResponse
)
from backend.app.services.ranking import get_current_weights, rank_events
from backend.app.services.explainer import generate_explanation
from backend.app.services.audit_logger import log_audit
from backend.app.config import settings

router = APIRouter(prefix="/api/triage", tags=["Triage"])

async def execute_triage_pipeline(db: Session, batch_id: Optional[str] = None) -> TriageSnapshot:
    """
    Executes the full triage and prioritization pipeline:
    1. Fetch recent events (up to 100)
    2. Score & rank items with current weights
    3. Generate Gen-AI / template explanations for top N items
    4. Persist snapshot for replay capability
    5. Audit log step with execution time (< 5-second SLA verification)
    """
    start_time = time.perf_counter()
    
    # 1. Fetch latest events
    events = db.query(Event).order_by(Event.ingested_at.desc()).limit(100).all()
    if not events:
        snapshot = TriageSnapshot(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            batch_id=batch_id,
            total_events_evaluated=0,
            weights_applied=get_current_weights(db),
            summary="No events in database to triage.",
            execution_time_ms=0.0
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    # 2. Get weights and rank events
    weights = get_current_weights(db)
    ranked_items = rank_events(events, weights)
    
    # 3. Create snapshot record
    snapshot_id = str(uuid.uuid4())
    snapshot = TriageSnapshot(
        id=snapshot_id,
        created_at=datetime.now(timezone.utc),
        batch_id=batch_id,
        total_events_evaluated=len(events),
        weights_applied=weights,
        summary=f"Triaged {len(events)} events across {len(set(e.stream_source for e in events))} streams."
    )
    db.add(snapshot)
    
    # 4. Process explanations for top N items
    top_n = settings.TOP_N_EXPLANATIONS
    for item in ranked_items:
        event = item["event"]
        rank = item["rank"]
        
        if rank <= top_n:
            explanation, action = await generate_explanation(event, item)
        else:
            explanation = f"Rank #{rank} priority event on {event.service}. Severity: {event.severity}."
            action = f"Monitor service '{event.service}' status."
            
        triage_item = TriageItem(
            snapshot_id=snapshot_id,
            event_id=event.id,
            rank=rank,
            priority_score=item["priority_score"],
            severity_score=item["severity_score"],
            blast_radius_score=item["blast_radius_score"],
            anomaly_score=item["anomaly_score"],
            recurrence_score=item["recurrence_score"],
            explanation=explanation,
            suggested_action=action,
            status="open"
        )
        db.add(triage_item)

    db.commit()
    
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    snapshot.execution_time_ms = elapsed_ms
    db.commit()
    db.refresh(snapshot)

    # 5. Record structured audit log
    log_audit(
        db=db,
        action="RUN_TRIAGE",
        actor="system",
        details={
            "snapshot_id": snapshot_id,
            "total_evaluated": len(events),
            "top_priority_score": ranked_items[0]["priority_score"] if ranked_items else 0,
            "top_event_id": ranked_items[0]["event"].id if ranked_items else None
        },
        execution_time_ms=elapsed_ms
    )

    return snapshot

@router.get("/current", response_model=TriageCurrentResponse)
async def get_current_triage(db: Session = Depends(get_db)):
    """
    Get the most recent triage snapshot with prioritized events and AI explanations.
    If none exists, executes a fresh triage run.
    """
    snapshot = db.query(TriageSnapshot).order_by(TriageSnapshot.created_at.desc()).first()
    
    if not snapshot:
        snapshot = await execute_triage_pipeline(db)

    # Build response
    items_response = []
    for item in snapshot.items:
        items_response.append(
            TriageItemResponse(
                id=item.id,
                event_id=item.event_id,
                rank=item.rank,
                priority_score=item.priority_score,
                severity_score=item.severity_score,
                blast_radius_score=item.blast_radius_score,
                anomaly_score=item.anomaly_score,
                recurrence_score=item.recurrence_score,
                explanation=item.explanation,
                suggested_action=item.suggested_action,
                status=item.status,
                event=EventResponse.model_validate(item.event)
            )
        )

    return TriageCurrentResponse(
        snapshot_id=snapshot.id,
        created_at=snapshot.created_at,
        total_events_evaluated=snapshot.total_events_evaluated,
        weights_applied=snapshot.weights_applied or {},
        execution_time_ms=snapshot.execution_time_ms,
        summary=snapshot.summary,
        items=items_response
    )

@router.get("/history", response_model=TriageHistoryResponse)
def get_triage_history(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """
    Retrieve historical triage snapshots for replaying past prioritization decisions.
    """
    snapshots = db.query(TriageSnapshot).order_by(TriageSnapshot.created_at.desc()).limit(limit).all()
    
    summaries = []
    for s in snapshots:
        top_item = s.items[0] if s.items else None
        top_title = top_item.event.title if top_item and top_item.event else None
        top_sev = top_item.event.severity if top_item and top_item.event else None
        
        summaries.append(
            TriageSnapshotSummary(
                id=s.id,
                created_at=s.created_at,
                total_events_evaluated=s.total_events_evaluated,
                weights_applied=s.weights_applied or {},
                execution_time_ms=s.execution_time_ms,
                top_incident_title=top_title,
                top_incident_severity=top_sev
            )
        )

    return TriageHistoryResponse(
        total_snapshots=len(summaries),
        snapshots=summaries
    )

@router.get("/replay/{snapshot_id}", response_model=TriageCurrentResponse)
def replay_snapshot(snapshot_id: str, db: Session = Depends(get_db)):
    """
    Replay a specific historical triage snapshot with all its rankings and items.
    """
    snapshot = db.query(TriageSnapshot).filter(TriageSnapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Triage snapshot with id '{snapshot_id}' not found."
        )

    items_response = [
        TriageItemResponse(
            id=item.id,
            event_id=item.event_id,
            rank=item.rank,
            priority_score=item.priority_score,
            severity_score=item.severity_score,
            blast_radius_score=item.blast_radius_score,
            anomaly_score=item.anomaly_score,
            recurrence_score=item.recurrence_score,
            explanation=item.explanation,
            suggested_action=item.suggested_action,
            status=item.status,
            event=EventResponse.model_validate(item.event)
        )
        for item in snapshot.items
    ]

    return TriageCurrentResponse(
        snapshot_id=snapshot.id,
        created_at=snapshot.created_at,
        total_events_evaluated=snapshot.total_events_evaluated,
        weights_applied=snapshot.weights_applied or {},
        execution_time_ms=snapshot.execution_time_ms,
        summary=snapshot.summary,
        items=items_response
    )
