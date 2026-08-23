from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import time
import uuid
from typing import Optional, List

from backend.app.database import get_db
from backend.app.models import Event, TriageSnapshot, TriageItem
from backend.app.schemas import (
    TriageCurrentResponse,
    TriageHistoryResponse,
    TriageSnapshotSummary,
    TriageItemResponse,
    EventResponse,
    ScoreBreakdown
)
from backend.app.services.ranking import get_current_weights, rank_events
from backend.app.services.explainer import generate_explanation
from backend.app.services.audit_logger import log_audit
from backend.app.config import settings

router = APIRouter(prefix="/api/triage", tags=["Triage"])

async def execute_triage_pipeline(db: Session, batch_id: Optional[str] = None) -> TriageSnapshot:
    """
    Executes the 5-signal triage and prioritization pipeline:
    1. Fetch recent events (up to 100)
    2. Score & rank items with active weights
    3. Generate AI / template explanations for top N items
    4. Persist snapshot for replay capability
    5. Audit log step with execution time (< 5-second SLA tracking)
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
        summary=f"Triaged {len(events)} events across {len(set(e.source for e in events))} streams."
    )
    db.add(snapshot)
    
    # 4. Process explanations for top N items
    top_n = settings.TOP_N_EXPLANATIONS
    for item in ranked_items:
        event = item["event"]
        rank = item["rank"]
        
        if rank <= top_n:
            explanation, exp_type, action = await generate_explanation(event, item)
        else:
            explanation = f"Rank #{rank} priority event on {event.service}. Severity: {event.severity}."
            exp_type = "template"
            action = f"Monitor service '{event.service}' status."
            
        triage_item = TriageItem(
            snapshot_id=snapshot_id,
            event_id=event.id,
            rank=rank,
            priority_score=item["score"],
            score_breakdown=item["score_breakdown"],
            explanation=explanation,
            explanation_type=exp_type,
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
    top_score = ranked_items[0]["score"] if ranked_items else 0.0
    top_evt = ranked_items[0]["event"] if ranked_items else None
    log_audit(
        db=db,
        action="RUN_TRIAGE",
        step="ranking",
        level="info",
        actor="system",
        message=f"Scored and ranked {len(events)} events (top score: {top_score}).",
        details={
            "snapshot_id": snapshot_id,
            "total_scored": len(events),
            "top_score": top_score,
            "top_event_id": top_evt.id if top_evt else None
        },
        execution_time_ms=elapsed_ms
    )

    return snapshot

def _build_triage_current_response(
    snapshot: TriageSnapshot,
    limit: Optional[int] = None,
    min_score: Optional[float] = None,
    source: Optional[str] = None
) -> TriageCurrentResponse:
    """Build unified TriageCurrentResponse matching API_SCHEMA.md & FRONTEND_PRD.md."""
    items = snapshot.items
    
    # Filter by source if requested
    if source:
        items = [i for i in items if i.event and i.event.source == source]
        
    # Filter by min_score if requested
    if min_score is not None:
        items = [i for i in items if i.priority_score >= min_score]
        
    # Apply limit
    if limit is not None:
        items = items[:limit]

    items_response = []
    for item in items:
        event_obj = item.event
        breakdown = item.score_breakdown or {}
        items_response.append(
            TriageItemResponse(
                id=item.id,
                event_id=item.event_id,
                source=event_obj.source if event_obj else "unknown",
                timestamp=event_obj.timestamp if event_obj else datetime.now(timezone.utc),
                severity=event_obj.severity if event_obj else "medium",
                service=event_obj.service if event_obj else "unknown",
                region=event_obj.region if event_obj else "global",
                title=event_obj.title if event_obj else "Event",
                details=event_obj.details if event_obj else {},
                tags=event_obj.tags if event_obj else [],
                score=item.priority_score,
                priority_score=item.priority_score,
                score_breakdown=ScoreBreakdown(
                    severity=breakdown.get("severity", 0.0),
                    frequency=breakdown.get("frequency", 0.0),
                    recency=breakdown.get("recency", 0.0),
                    anomaly=breakdown.get("anomaly", 0.0),
                    business_impact=breakdown.get("business_impact", 0.0)
                ),
                rank=item.rank,
                explanation=item.explanation,
                explanation_type=item.explanation_type or "template",
                suggested_action=item.suggested_action,
                status=item.status,
                event=EventResponse.model_validate(event_obj) if event_obj else None
            )
        )

    weights = snapshot.weights_applied or {}
    return TriageCurrentResponse(
        triage_id=snapshot.id,
        snapshot_id=snapshot.id,
        generated_at=snapshot.created_at,
        created_at=snapshot.created_at,
        total_events=snapshot.total_events_evaluated,
        total_events_evaluated=snapshot.total_events_evaluated,
        weights_used=weights,
        weights_applied=weights,
        execution_time_ms=snapshot.execution_time_ms,
        summary=snapshot.summary,
        ranked_events=items_response,
        items=items_response
    )

@router.get("/current", response_model=TriageCurrentResponse)
async def get_current_triage(
    limit: Optional[int] = Query(None, description="Max events to return"),
    min_score: Optional[float] = Query(None, description="Filter events below this score"),
    source: Optional[str] = Query(None, description="Filter by stream source"),
    db: Session = Depends(get_db)
):
    """
    Get the current ranked/prioritized events with explanations and score breakdown.
    Supports filtering by limit, min_score, and source.
    """
    snapshot = db.query(TriageSnapshot).order_by(TriageSnapshot.created_at.desc()).first()
    if not snapshot:
        snapshot = await execute_triage_pipeline(db)

    return _build_triage_current_response(snapshot, limit=limit, min_score=min_score, source=source)

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
        top_score = top_item.priority_score if top_item else None
        
        summaries.append(
            TriageSnapshotSummary(
                triage_id=s.id,
                id=s.id,
                generated_at=s.created_at,
                created_at=s.created_at,
                total_events=s.total_events_evaluated,
                total_events_evaluated=s.total_events_evaluated,
                weights_used=s.weights_applied or {},
                execution_time_ms=s.execution_time_ms,
                top_event_title=top_title,
                top_incident_title=top_title,
                top_score=top_score
            )
        )

    return TriageHistoryResponse(
        total_snapshots=len(summaries),
        history=summaries,
        snapshots=summaries
    )

@router.get("/history/{triage_id}", response_model=TriageCurrentResponse)
def get_triage_snapshot_by_id(triage_id: str, db: Session = Depends(get_db)):
    """
    Get full details of a past triage snapshot (matches API_SCHEMA.md).
    """
    snapshot = db.query(TriageSnapshot).filter(TriageSnapshot.id == triage_id).first()
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Triage snapshot with ID '{triage_id}' not found."
        )
    return _build_triage_current_response(snapshot)

@router.get("/replay/{snapshot_id}", response_model=TriageCurrentResponse)
def replay_snapshot(snapshot_id: str, db: Session = Depends(get_db)):
    """
    Replay a specific historical triage snapshot with all its rankings and items.
    """
    return get_triage_snapshot_by_id(snapshot_id, db)
