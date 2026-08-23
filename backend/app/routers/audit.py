from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.database import get_db
from backend.app.models import AuditLog
from backend.app.schemas import AuditLogResponse, AuditLogEntry

router = APIRouter(prefix="/api", tags=["Audit Log"])

@router.get("/audit-log", response_model=AuditLogResponse)
def get_audit_logs(
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
    level: Optional[str] = Query(None, description="Filter by log level: info, warning, error"),
    db: Session = Depends(get_db)
):
    """
    Retrieve structured audit log records documenting ingestion, triage, and feedback actions.
    Supports filtering by log level.
    """
    query = db.query(AuditLog)
    if level:
        query = query.filter(AuditLog.level == level.lower())
        
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    entries = []
    for log in logs:
        entries.append(
            AuditLogEntry(
                id=log.id,
                timestamp=log.timestamp,
                level=log.level or "info",
                step=log.step or "ingest",
                action=log.action,
                actor=log.actor or "system",
                message=log.message or f"{log.action} completed",
                details=log.details or {},
                duration_ms=log.execution_time_ms or 0.0,
                execution_time_ms=log.execution_time_ms or 0.0
            )
        )
    
    return AuditLogResponse(
        total=len(entries),
        logs=entries
    )
