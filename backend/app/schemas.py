from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime

# ==================== EVENT SCHEMAS ====================

class EventBase(BaseModel):
    stream_source: str = Field(..., description="Source stream e.g., 'infra_apm', 'auth_security', 'app_business'")
    event_type: str = Field(..., description="Type of event e.g., 'high_cpu', 'failed_login_burst', 'payment_latency'")
    severity: str = Field("medium", description="Severity: 'critical', 'high', 'medium', 'low', 'info'")
    service: str = Field(..., description="Affected service name e.g., 'auth-service', 'payment-gateway'")
    environment: str = Field("production", description="Environment: 'production', 'staging'")
    region: str = Field("global", description="Cloud region e.g., 'us-east-1', 'eu-west-1'")
    title: str = Field(..., description="Short summary title of the event")
    description: Optional[str] = Field("", description="Detailed description")
    raw_payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Raw event payload / telemetry")

class EventCreate(EventBase):
    id: Optional[str] = Field(None, description="Optional custom event ID, auto-generated if omitted")
    timestamp: Optional[datetime] = Field(None, description="Event occurrence timestamp (UTC)")

class EventResponse(EventBase):
    id: str
    timestamp: datetime
    ingested_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EventIngestRequest(BaseModel):
    events: List[EventCreate] = Field(..., description="List of events to ingest")
    trigger_triage: bool = Field(True, description="Whether to automatically re-run triage on ingestion")

class EventIngestResponse(BaseModel):
    ingested_count: int
    batch_id: Optional[str] = None
    message: str
    events: List[EventResponse]

# ==================== TRIAGE SCHEMAS ====================

class TriageItemResponse(BaseModel):
    id: int
    event_id: str
    rank: int
    priority_score: float
    severity_score: float
    blast_radius_score: float
    anomaly_score: float
    recurrence_score: float
    explanation: str
    suggested_action: str
    status: str
    event: EventResponse

    model_config = ConfigDict(from_attributes=True)

class TriageCurrentResponse(BaseModel):
    snapshot_id: str
    created_at: datetime
    total_events_evaluated: int
    weights_applied: Dict[str, float]
    execution_time_ms: float
    summary: Optional[str] = None
    items: List[TriageItemResponse]

    model_config = ConfigDict(from_attributes=True)

class TriageSnapshotSummary(BaseModel):
    id: str
    created_at: datetime
    total_events_evaluated: int
    weights_applied: Dict[str, float]
    execution_time_ms: float
    top_incident_title: Optional[str] = None
    top_incident_severity: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class TriageHistoryResponse(BaseModel):
    total_snapshots: int
    snapshots: List[TriageSnapshotSummary]

# ==================== WEIGHT / FEEDBACK SCHEMAS ====================

class FeedbackRequest(BaseModel):
    severity_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    blast_radius_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    anomaly_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    recurrence_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    operator_notes: Optional[str] = Field(None, description="Optional feedback rationale")
    re_triage_now: bool = Field(True, description="Whether to re-evaluate triage immediately with new weights")

class WeightResponse(BaseModel):
    severity_weight: float
    blast_radius_weight: float
    anomaly_weight: float
    recurrence_weight: float
    updated_at: datetime
    updated_by: str

    model_config = ConfigDict(from_attributes=True)

class FeedbackResponse(BaseModel):
    status: str
    message: str
    weights: WeightResponse
    new_snapshot_id: Optional[str] = None

# ==================== AUDIT LOG SCHEMAS ====================

class AuditLogEntry(BaseModel):
    id: int
    timestamp: datetime
    action: str
    actor: str
    details: Dict[str, Any]
    execution_time_ms: float

    model_config = ConfigDict(from_attributes=True)

class AuditLogResponse(BaseModel):
    total: int
    logs: List[AuditLogEntry]

# ==================== HEALTH SCHEMAS ====================

class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    database: str
    timestamp: datetime
