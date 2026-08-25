from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EvidenceSource = Literal["metric", "log", "trace", "deployment", "commit", "runbook"]


class Evidence(BaseModel):
    evidence_id: str
    source: EvidenceSource
    service: str
    timestamp_start: datetime
    timestamp_end: datetime
    observation: str
    raw_reference: str
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    investigation_id: str | None = None


class TimelineEvent(BaseModel):
    event_id: str
    investigation_id: str
    occurred_at: datetime
    summary: str
    evidence_id: str | None = None
