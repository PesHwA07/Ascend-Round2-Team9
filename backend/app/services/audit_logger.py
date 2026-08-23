from sqlalchemy.orm import Session
from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional

from backend.app.models import AuditLog

logger = logging.getLogger("aurabrief.audit")

def log_audit(
    db: Session,
    action: str,
    actor: str = "system",
    details: Optional[Dict[str, Any]] = None,
    execution_time_ms: float = 0.0
) -> AuditLog:
    """Record an audit trail log in SQLite database and application logger."""
    if details is None:
        details = {}
        
    entry = AuditLog(
        timestamp=datetime.now(timezone.utc),
        action=action,
        actor=actor,
        details=details,
        execution_time_ms=execution_time_ms
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    logger.info(f"AUDIT [{action}] by [{actor}] ({execution_time_ms:.2f}ms): {details}")
    return entry
