from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import time
import uuid

from backend.app.database import get_db
from backend.app.models import Event
from backend.app.schemas import EventIngestRequest, EventIngestResponse, EventResponse
from backend.app.services.audit_logger import log_audit

router = APIRouter(prefix="/api/events", tags=["Ingest"])

@router.post("/ingest", response_model=EventIngestResponse, status_code=status.HTTP_200_OK)
async def ingest_events(request: EventIngestRequest, db: Session = Depends(get_db)):
    """
    Ingest a batch of simulated events from any of the 3 event streams (infra-monitor, app-errors, deploy-events).
    Accepts simulator batches and triggers immediate triage update.
    """
    start_time = time.perf_counter()
    batch_id = str(uuid.uuid4())
    saved_events = []
    
    try:
        for event_data in request.events:
            event_dict = event_data.model_dump()
            
            # Resolve event_id and timestamp
            event_id = event_dict.get("event_id") or event_dict.get("id") or str(uuid.uuid4())
            ts = event_dict.get("timestamp") or datetime.now(timezone.utc)
            source = event_dict.get("source") or event_dict.get("stream_source") or "general"
            details = event_dict.get("details") or event_dict.get("raw_payload") or {}
            tags = event_dict.get("tags") or []
            
            event_obj = Event(
                id=event_id,
                source=source,
                timestamp=ts,
                event_type=event_dict.get("event_type") or "general_event",
                severity=event_dict.get("severity", "medium").lower(),
                service=event_dict["service"],
                environment=event_dict.get("environment", "production"),
                region=event_dict.get("region", "global"),
                title=event_dict["title"],
                description=event_dict.get("description", ""),
                details=details,
                tags=tags,
                ingested_at=datetime.now(timezone.utc)
            )
            db.add(event_obj)
            saved_events.append(event_obj)

        db.commit()
        for e in saved_events:
            db.refresh(e)
            
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        
        # Trigger immediate triage if requested
        if request.trigger_triage:
            from backend.app.routers.triage import execute_triage_pipeline
            await execute_triage_pipeline(db, batch_id=batch_id)

        # Audit log the ingestion step
        log_audit(
            db=db,
            action="INGEST_EVENTS",
            step="ingest",
            level="info",
            actor="simulator",
            message=f"Received and ingested {len(saved_events)} events from streams.",
            details={
                "batch_id": batch_id,
                "count": len(saved_events),
                "sources": list(set(e.source for e in saved_events))
            },
            execution_time_ms=elapsed_ms
        )

        event_ids = [e.id for e in saved_events]

        return EventIngestResponse(
            status="accepted",
            received_count=len(saved_events),
            event_ids=event_ids,
            ingested_count=len(saved_events),
            batch_id=batch_id,
            message=f"Successfully ingested {len(saved_events)} events across streams.",
            events=[EventResponse.model_validate(e) for e in saved_events]
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest events: {str(e)}"
        )
