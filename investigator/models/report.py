from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Report(BaseModel):
    report_id: str
    investigation_id: str
    incident_id: str
    alert_name: str
    root_cause: str
    root_service: str
    confidence: float
    hypothesis_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    body: str = ""
    created_at: datetime
