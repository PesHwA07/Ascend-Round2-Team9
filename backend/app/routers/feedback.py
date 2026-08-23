from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import time

from backend.app.database import get_db
from backend.app.schemas import FeedbackRequest, FeedbackResponse, WeightResponse
from backend.app.services.ranking import get_current_weights, update_weights
from backend.app.services.audit_logger import log_audit

router = APIRouter(prefix="/api", tags=["Feedback & Weights"])

@router.get("/weights", response_model=WeightResponse)
def get_weights(db: Session = Depends(get_db)):
    """
    Get the currently active 5-signal ranking weights.
    """
    weights = get_current_weights(db)
    return WeightResponse(
        weights=weights,
        severity=weights["severity"],
        frequency=weights["frequency"],
        recency=weights["recency"],
        anomaly=weights["anomaly"],
        business_impact=weights["business_impact"],
        updated_at=datetime.now(timezone.utc),
        updated_by="system"
    )

@router.post("/feedback", response_model=FeedbackResponse)
async def submit_operator_feedback(request: FeedbackRequest, db: Session = Depends(get_db)):
    """
    Adjust ranking weights via operator feedback loop (Bonus Scope).
    Immediately returns re-ranked events matching Frontend PRD requirement.
    """
    start_time = time.perf_counter()
    try:
        previous_weights = get_current_weights(db)
        
        updated_config = update_weights(
            db=db,
            severity=request.severity,
            frequency=request.frequency,
            recency=request.recency,
            anomaly=request.anomaly,
            business_impact=request.business_impact,
            actor="operator"
        )
        
        new_weights = {
            "severity": updated_config.severity,
            "frequency": updated_config.frequency,
            "recency": updated_config.recency,
            "anomaly": updated_config.anomaly,
            "business_impact": updated_config.business_impact
        }
        
        ranked_events_response = None
        new_snapshot_id = None
        
        if request.re_triage_now:
            from backend.app.routers.triage import execute_triage_pipeline, _build_triage_current_response
            new_snapshot = await execute_triage_pipeline(db)
            new_snapshot_id = new_snapshot.id
            curr_resp = _build_triage_current_response(new_snapshot)
            ranked_events_response = curr_resp.ranked_events
            
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        
        # Log to audit trail
        log_audit(
            db=db,
            action="UPDATE_WEIGHTS",
            step="feedback",
            level="info",
            actor="operator",
            message="Operator adjusted ranking weights and triggered re-triage.",
            details={
                "notes": request.operator_notes,
                "previous_weights": previous_weights,
                "new_weights": new_weights,
                "triggered_re_triage": request.re_triage_now,
                "new_snapshot_id": new_snapshot_id
            },
            execution_time_ms=elapsed_ms
        )

        return FeedbackResponse(
            status="weights_updated",
            previous_weights=previous_weights,
            new_weights=new_weights,
            weights=new_weights,
            message="Rankings will reflect new weights on next triage refresh.",
            new_snapshot_id=new_snapshot_id,
            ranked_events=ranked_events_response
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply feedback: {str(e)}"
        )
