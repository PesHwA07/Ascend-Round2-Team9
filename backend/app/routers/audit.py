from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import AuditLog
from backend.app.schemas import AuditLogResponse, AuditLogEntry

router = APIRouter(prefix="/api", tags=["Audit Log"])

@router.get("/audit-log", response_model=AuditLogResponse)
def get_audit_logs(
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
    db: Session = Depends(get_db)
):
    """
    Retrieve structured audit log records documenting ingestion, triage, and feedback actions.
    """
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    return AuditLogResponse(
        total=len(logs),
        logs=[AuditLogEntry.model_validate(log) for log in logs]
    )
