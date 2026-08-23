from sqlalchemy.orm import Session
from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional

from backend.app.models import AuditLog

logger = logging.getLogger("aurabrief.audit")

def log_audit(
    db: Session,
    action: str,
    step: str = "ingest",
    level: str = "info",
    actor: str = "system",
    message: str = "",
    details: Optional[Dict[str, Any]] = None,
    execution_time_ms: float = 0.0
) -> AuditLog:
    """Record an audit trail log in SQLite database and application logger."""
    if details is None:
        details = {}
        
    if not message:
        message = f"Executed {action} step [{step}] by {actor}"

    entry = AuditLog(
        timestamp=datetime.now(timezone.utc),
        level=level,
        step=step,
        action=action,
        actor=actor,
        message=message,
        details=details,
        execution_time_ms=round(execution_time_ms, 2)
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    logger.info(f"AUDIT [{level.upper()}] [{step}] [{action}] by [{actor}] ({execution_time_ms:.2f}ms): {message}")
    return entry
