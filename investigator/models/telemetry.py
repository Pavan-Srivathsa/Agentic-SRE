from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class MetricPoint(BaseModel):
    timestamp: datetime
    value: float


class MetricSeries(BaseModel):
    metric: str
    service: str
    aggregation: str
    points: list[MetricPoint] = Field(default_factory=list)
    query: str = ""


class LogEvent(BaseModel):
    timestamp: datetime
    service: str
    severity: str
    message: str
    trace_id: str | None = None
    raw_reference: str = ""


class SpanNode(BaseModel):
    span_id: str
    name: str
    service: str
    duration_ms: float
    children: list[SpanNode] = Field(default_factory=list)


class TraceSummary(BaseModel):
    trace_id: str
    root_service: str
    duration_ms: float
    start_time: datetime | None = None


class TraceTree(BaseModel):
    trace_id: str
    duration_ms: float
    root: SpanNode | None = None
    services: list[str] = Field(default_factory=list)


class Deployment(BaseModel):
    deployment_id: str
    service: str
    version: str
    commit_sha: str
    deployed_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommitDiff(BaseModel):
    commit_sha: str
    service: str
    author: str
    message: str
    committed_at: datetime
    files_changed: list[str] = Field(default_factory=list)
    diff_summary: str = ""


class ConnectorError(BaseModel):
    connector: str
    message: str
    retryable: bool = True


MetricName = Literal[
    "request_rate",
    "error_rate",
    "request_latency",
    "cpu",
    "memory",
    "database_latency",
    "connection_pool_utilization",
    "queue_depth",
    "dependency_latency",
]
