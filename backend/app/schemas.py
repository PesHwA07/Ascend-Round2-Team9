from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone

# ==================== EVENT SCHEMAS ====================

class EventBase(BaseModel):
    source: str = Field(..., description="Source stream e.g., 'infra-monitor', 'app-errors', 'deploy-events'")
    severity: str = Field("medium", description="Severity: 'critical', 'warning', 'high', 'medium', 'low', 'info'")
    service: str = Field(..., description="Affected service name e.g., 'payment-api', 'auth-gateway', 'gateway'")
    region: str = Field("global", description="Cloud region e.g., 'us-east', 'eu-west', 'global'")
    title: str = Field(..., description="Short summary title of the event")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Stream-specific telemetry payload")
    tags: Optional[List[str]] = Field(default_factory=list, description="Categorization tags")
    
    # Optional extended metadata
    event_type: Optional[str] = Field(None, description="Event type identifier")
    environment: Optional[str] = Field("production", description="Environment: 'production', 'staging'")
    description: Optional[str] = Field("", description="Detailed narrative description")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

class EventCreate(EventBase):
    event_id: Optional[str] = Field(None, description="Custom event UUID (auto-generated if omitted)")
    id: Optional[str] = Field(None, description="Alias for event_id")
    timestamp: Optional[datetime] = Field(None, description="Event timestamp (UTC ISO-8601)")
    stream_source: Optional[str] = Field(None, description="Alias for source")
    raw_payload: Optional[Dict[str, Any]] = Field(None, description="Alias for details")

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Resolve event_id vs id
            if "event_id" in values and values["event_id"] and not values.get("id"):
                values["id"] = values["event_id"]
            elif "id" in values and values["id"] and not values.get("event_id"):
                values["event_id"] = values["id"]

            # Resolve source vs stream_source
            if "source" in values and values["source"] and not values.get("stream_source"):
                values["stream_source"] = values["source"]
            elif "stream_source" in values and values["stream_source"] and not values.get("source"):
                values["source"] = values["stream_source"]

            # Resolve details vs raw_payload
            if "details" in values and values["details"] and not values.get("raw_payload"):
                values["raw_payload"] = values["details"]
            elif "raw_payload" in values and values["raw_payload"] and not values.get("details"):
                values["details"] = values["raw_payload"]

            # Default event_type if missing
            if not values.get("event_type"):
                det = values.get("details") or {}
                values["event_type"] = det.get("error_type") or det.get("deploy_type") or det.get("metric_name") or "general_event"
        return values

class EventResponse(EventBase):
    event_id: str
    id: str
    timestamp: datetime
    ingested_at: datetime
    stream_source: str
    raw_payload: Dict[str, Any]

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_response_aliases(cls, obj: Any) -> Any:
        if hasattr(obj, "id"):
            return {
                "event_id": obj.id,
                "id": obj.id,
                "source": obj.source,
                "stream_source": obj.source,
                "timestamp": obj.timestamp,
                "severity": obj.severity,
                "service": obj.service,
                "region": obj.region,
                "title": obj.title,
                "details": obj.details or {},
                "raw_payload": obj.details or {},
                "tags": obj.tags or [],
                "event_type": obj.event_type or "general_event",
                "environment": obj.environment or "production",
                "description": obj.description or "",
                "ingested_at": obj.ingested_at or datetime.now(timezone.utc)
            }
        return obj

class EventIngestRequest(BaseModel):
    events: List[EventCreate] = Field(..., description="List of events to ingest")
    trigger_triage: bool = Field(True, description="Whether to immediately run triage on ingestion")

class EventIngestResponse(BaseModel):
    status: str = "accepted"
    received_count: int
    event_ids: List[str]
    ingested_count: int
    batch_id: Optional[str] = None
    message: str
    events: List[EventResponse]

# ==================== TRIAGE SCHEMAS ====================

class ScoreBreakdown(BaseModel):
    severity: float = 0.0
    frequency: float = 0.0
    recency: float = 0.0
    anomaly: float = 0.0
    business_impact: float = 0.0

class TriageItemResponse(BaseModel):
    id: int
    event_id: str
    source: str
    timestamp: datetime
    severity: str
    service: str
    region: str
    title: str
    details: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    score: float
    priority_score: float
    score_breakdown: ScoreBreakdown
    rank: int
    explanation: str
    explanation_type: str = "template" # 'ai' | 'template'
    suggested_action: str
    status: str
    event: Optional[EventResponse] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

class TriageCurrentResponse(BaseModel):
    triage_id: str
    snapshot_id: str
    generated_at: datetime
    created_at: datetime
    total_events: int
    total_events_evaluated: int
    weights_used: Dict[str, float]
    weights_applied: Dict[str, float]
    execution_time_ms: float
    summary: Optional[str] = None
    ranked_events: List[TriageItemResponse]
    items: List[TriageItemResponse]

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

class TriageSnapshotSummary(BaseModel):
    triage_id: str
    id: str
    generated_at: datetime
    created_at: datetime
    total_events: int
    total_events_evaluated: int
    weights_used: Dict[str, float]
    execution_time_ms: float
    top_event_title: Optional[str] = None
    top_incident_title: Optional[str] = None
    top_score: Optional[float] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

class TriageHistoryResponse(BaseModel):
    total_snapshots: int
    history: List[TriageSnapshotSummary]
    snapshots: List[TriageSnapshotSummary]

# ==================== WEIGHT / FEEDBACK SCHEMAS ====================

class WeightsDict(BaseModel):
    severity: float = Field(0.30, ge=0.0, le=1.0)
    frequency: float = Field(0.20, ge=0.0, le=1.0)
    recency: float = Field(0.15, ge=0.0, le=1.0)
    anomaly: float = Field(0.20, ge=0.0, le=1.0)
    business_impact: float = Field(0.15, ge=0.0, le=1.0)

class FeedbackRequest(BaseModel):
    weights: Optional[Dict[str, float]] = None
    severity: Optional[float] = Field(None, ge=0.0, le=1.0)
    frequency: Optional[float] = Field(None, ge=0.0, le=1.0)
    recency: Optional[float] = Field(None, ge=0.0, le=1.0)
    anomaly: Optional[float] = Field(None, ge=0.0, le=1.0)
    business_impact: Optional[float] = Field(None, ge=0.0, le=1.0)
    operator_notes: Optional[str] = None
    re_triage_now: bool = Field(True, description="Whether to re-rank events immediately")

    @model_validator(mode="before")
    @classmethod
    def parse_feedback_weights(cls, values: Any) -> Any:
        if isinstance(values, dict):
            w = values.get("weights")
            if isinstance(w, dict):
                for k in ["severity", "frequency", "recency", "anomaly", "business_impact"]:
                    if k in w and values.get(k) is None:
                        values[k] = w[k]
        return values

class WeightResponse(BaseModel):
    weights: Dict[str, float]
    severity: float
    frequency: float
    recency: float
    anomaly: float
    business_impact: float
    updated_at: datetime
    updated_by: str

class FeedbackResponse(BaseModel):
    status: str = "weights_updated"
    previous_weights: Dict[str, float]
    new_weights: Dict[str, float]
    weights: Dict[str, float]
    message: str
    new_snapshot_id: Optional[str] = None
    ranked_events: Optional[List[TriageItemResponse]] = None

# ==================== AUDIT LOG SCHEMAS ====================

class AuditLogEntry(BaseModel):
    id: int
    timestamp: datetime
    level: str = "info"
    step: str = "ingest"
    action: str
    actor: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    execution_time_ms: float = 0.0

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

class AuditLogResponse(BaseModel):
    total: int
    logs: List[AuditLogEntry]

# ==================== HEALTH SCHEMAS ====================

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "aurabrief-backend"
    app_name: str = "AuraBrief 95"
    version: str = "1.0.0"
    database: str = "connected"
    timestamp: datetime
