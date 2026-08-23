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
    Get the currently active ranking weights.
    """
    weights = get_current_weights(db)
    return WeightResponse(
        severity_weight=weights["severity_weight"],
        blast_radius_weight=weights["blast_radius_weight"],
        anomaly_weight=weights["anomaly_weight"],
        recurrence_weight=weights["recurrence_weight"],
        updated_at=datetime.now(timezone.utc),
        updated_by="system"
    )

@router.post("/feedback", response_model=FeedbackResponse)
async def submit_operator_feedback(request: FeedbackRequest, db: Session = Depends(get_db)):
    """
    Adjust ranking weights via operator feedback loop (Bonus Scope).
    Optionally triggers immediate re-triage of current events.
    """
    start_time = time.perf_counter()
    try:
        updated_config = update_weights(
            db=db,
            severity_weight=request.severity_weight,
            blast_radius_weight=request.blast_radius_weight,
            anomaly_weight=request.anomaly_weight,
            recurrence_weight=request.recurrence_weight,
            actor="operator"
        )
        
        new_snapshot_id = None
        if request.re_triage_now:
            from backend.app.routers.triage import execute_triage_pipeline
            new_snapshot = await execute_triage_pipeline(db)
            new_snapshot_id = new_snapshot.id
            
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        
        # Log to audit trail
        log_audit(
            db=db,
            action="UPDATE_WEIGHTS",
            actor="operator",
            details={
                "notes": request.operator_notes,
                "weights": {
                    "severity": updated_config.severity_weight,
                    "blast_radius": updated_config.blast_radius_weight,
                    "anomaly": updated_config.anomaly_weight,
                    "recurrence": updated_config.recurrence_weight
                },
                "triggered_re_triage": request.re_triage_now,
                "new_snapshot_id": new_snapshot_id
            },
            execution_time_ms=elapsed_ms
        )

        return FeedbackResponse(
            status="success",
            message="Ranking weights updated successfully.",
            weights=WeightResponse(
                severity_weight=updated_config.severity_weight,
                blast_radius_weight=updated_config.blast_radius_weight,
                anomaly_weight=updated_config.anomaly_weight,
                recurrence_weight=updated_config.recurrence_weight,
                updated_at=updated_config.updated_at,
                updated_by=updated_config.updated_by
            ),
            new_snapshot_id=new_snapshot_id
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply feedback: {str(e)}"
        )
