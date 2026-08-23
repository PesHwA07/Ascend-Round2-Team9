from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from backend.app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class Event(Base):
    __tablename__ = "events"

    id = Column(String(64), primary_key=True, default=generate_uuid, index=True)
    stream_source = Column(String(64), nullable=False, index=True)  # infra_apm, auth_security, app_business
    timestamp = Column(DateTime, default=utc_now, index=True)
    event_type = Column(String(128), nullable=False, index=True)
    severity = Column(String(32), nullable=False, default="medium", index=True) # critical, high, medium, low, info
    service = Column(String(128), nullable=False, index=True)
    environment = Column(String(32), default="production")
    region = Column(String(32), default="global")
    title = Column(String(256), nullable=False)
    description = Column(Text, default="")
    raw_payload = Column(JSON, default=dict)
    ingested_at = Column(DateTime, default=utc_now, index=True)

    triage_items = relationship("TriageItem", back_populates="event", cascade="all, delete-orphan")


class TriageSnapshot(Base):
    __tablename__ = "triage_snapshots"

    id = Column(String(64), primary_key=True, default=generate_uuid, index=True)
    created_at = Column(DateTime, default=utc_now, index=True)
    batch_id = Column(String(64), nullable=True)
    total_events_evaluated = Column(Integer, default=0)
    weights_applied = Column(JSON, default=dict)
    summary = Column(Text, nullable=True)
    execution_time_ms = Column(Float, default=0.0)

    items = relationship("TriageItem", back_populates="snapshot", cascade="all, delete-orphan", order_by="TriageItem.rank")


class TriageItem(Base):
    __tablename__ = "triage_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(64), ForeignKey("triage_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(String(64), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    
    rank = Column(Integer, nullable=False, index=True)
    priority_score = Column(Float, nullable=False)
    
    # Component breakdown scores (0.0 - 1.0 or 0 - 100)
    severity_score = Column(Float, default=0.0)
    blast_radius_score = Column(Float, default=0.0)
    anomaly_score = Column(Float, default=0.0)
    recurrence_score = Column(Float, default=0.0)
    
    explanation = Column(Text, default="")
    suggested_action = Column(Text, default="")
    status = Column(String(32), default="open") # open, acknowledged, resolved

    snapshot = relationship("TriageSnapshot", back_populates="items")
    event = relationship("Event", back_populates="triage_items")


class WeightConfig(Base):
    __tablename__ = "weight_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    severity_weight = Column(Float, nullable=False)
    blast_radius_weight = Column(Float, nullable=False)
    anomaly_weight = Column(Float, nullable=False)
    recurrence_weight = Column(Float, nullable=False)
    updated_by = Column(String(64), default="operator")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
    action = Column(String(64), nullable=False, index=True)
    actor = Column(String(64), default="system")
    details = Column(JSON, default=dict)
    execution_time_ms = Column(Float, default=0.0)
