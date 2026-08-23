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
    source = Column(String(64), nullable=False, index=True)  # infra-monitor, app-errors, deploy-events
    timestamp = Column(DateTime, default=utc_now, index=True)
    event_type = Column(String(128), default="general_event", index=True)
    severity = Column(String(32), nullable=False, default="medium", index=True) # critical, warning, high, medium, low, info
    service = Column(String(128), nullable=False, index=True)
    environment = Column(String(32), default="production")
    region = Column(String(64), default="global")
    title = Column(String(256), nullable=False)
    description = Column(Text, default="")
    details = Column(JSON, default=dict)
    tags = Column(JSON, default=list)
    ingested_at = Column(DateTime, default=utc_now, index=True)

    triage_items = relationship("TriageItem", back_populates="event", cascade="all, delete-orphan")

    @property
    def event_id(self) -> str:
        return self.id

    @property
    def stream_source(self) -> str:
        return self.source

    @property
    def raw_payload(self) -> dict:
        return self.details or {}


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
    
    # 5-Signal component breakdown scores (0.0 - 1.0)
    score_breakdown = Column(JSON, default=dict)
    
    explanation = Column(Text, default="")
    explanation_type = Column(String(32), default="template") # 'ai' | 'template'
    suggested_action = Column(Text, default="")
    status = Column(String(32), default="open") # open, acknowledged, resolved

    snapshot = relationship("TriageSnapshot", back_populates="items")
    event = relationship("Event", back_populates="triage_items")

    @property
    def score(self) -> float:
        return self.priority_score


class WeightConfig(Base):
    __tablename__ = "weight_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    severity = Column(Float, nullable=False, default=0.30)
    frequency = Column(Float, nullable=False, default=0.20)
    recency = Column(Float, nullable=False, default=0.15)
    anomaly = Column(Float, nullable=False, default=0.20)
    business_impact = Column(Float, nullable=False, default=0.15)
    updated_by = Column(String(64), default="operator")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
    level = Column(String(32), default="info") # info, warning, error
    step = Column(String(64), default="ingest") # ingest, ranking, explainer, feedback, system
    action = Column(String(64), nullable=False, index=True) # INGEST_EVENTS, RUN_TRIAGE, UPDATE_WEIGHTS
    actor = Column(String(64), default="system")
    message = Column(Text, default="")
    details = Column(JSON, default=dict)
    execution_time_ms = Column(Float, default=0.0)

    @property
    def duration_ms(self) -> float:
        return self.execution_time_ms
