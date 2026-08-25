from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    RECEIVED = "RECEIVED"
    SCOPING = "SCOPING"
    BASELINE_COLLECTION = "BASELINE_COLLECTION"
    HYPOTHESIS_GENERATION = "HYPOTHESIS_GENERATION"
    EVIDENCE_COLLECTION = "EVIDENCE_COLLECTION"
    VERIFICATION = "VERIFICATION"
    DIAGNOSED = "DIAGNOSED"
    REPORT_GENERATED = "REPORT_GENERATED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"


class AlertIngest(BaseModel):
    alert_id: str
    alert_name: str
    service: str
    severity: str
    starts_at: datetime
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)


class TimeWindow(BaseModel):
    start: datetime
    end: datetime


class Scope(BaseModel):
    primary_service: str
    services: list[str]
    incident: TimeWindow
    baseline: TimeWindow
    by_depth: dict[str, list[str]] = Field(default_factory=dict)


class Alert(BaseModel):
    alert_id: str
    alert_name: str
    service: str
    severity: str
    starts_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class Incident(BaseModel):
    incident_id: str
    alert_id: str
    service: str
    severity: str
    started_at: datetime
    status: IncidentStatus
    created_at: datetime
    investigation_id: str | None = None
    scope: Scope | None = None
    notes: str | None = None


class Investigation(BaseModel):
    investigation_id: str
    incident_id: str
    status: IncidentStatus
    created_at: datetime
    scope: Scope | None = None
    notes: str | None = None


class Transition(BaseModel):
    event_id: str
    investigation_id: str
    from_status: IncidentStatus | None
    to_status: IncidentStatus
    at: datetime
