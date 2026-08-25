from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

HypothesisStatus = Literal["candidate", "supported", "contradicted", "inconclusive"]


class Hypothesis(BaseModel):
    hypothesis_id: str
    title: str
    description: str
    affected_service: str
    confidence: float = 0.0
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)
    status: HypothesisStatus = "candidate"
    investigation_id: str | None = None
