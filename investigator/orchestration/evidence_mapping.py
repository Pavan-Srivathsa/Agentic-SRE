from __future__ import annotations

import uuid
from datetime import datetime

from investigator.models.evidence import Evidence, TimelineEvent
from investigator.models.telemetry import Deployment, LogEvent, MetricSeries, TraceSummary


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def observation_from_metric(series: MetricSeries) -> str:
    if not series.points:
        return f"{series.metric} for {series.service}: no data in window"
    last = series.points[-1]
    return f"{series.aggregation} {series.metric} last point {last.value:.4f} at {last.timestamp.isoformat()}"


def observation_from_log(event: LogEvent) -> str:
    snippet = event.message[:120].replace("\n", " ")
    return f"{event.severity} log on {event.service}: {snippet}"


def observation_from_deployment(deployment: Deployment) -> str:
    return (
        f"deployment {deployment.version} ({deployment.commit_sha[:7]}) "
        f"on {deployment.service} at {deployment.deployed_at.isoformat()}"
    )


def observation_from_trace(trace: TraceSummary) -> str:
    return f"slow trace {trace.trace_id[:12]} on {trace.root_service} duration {trace.duration_ms:.0f}ms"


def evidence_from_metric(
    series: MetricSeries,
    *,
    investigation_id: str,
    window_start: datetime,
    window_end: datetime,
) -> Evidence:
    return Evidence(
        evidence_id=_new_id("ev"),
        investigation_id=investigation_id,
        source="metric",
        service=series.service,
        timestamp_start=window_start,
        timestamp_end=window_end,
        observation=observation_from_metric(series),
        raw_reference=series.query or series.metric,
    )


def evidence_from_log(event: LogEvent, *, investigation_id: str, window_end: datetime) -> Evidence:
    return Evidence(
        evidence_id=_new_id("ev"),
        investigation_id=investigation_id,
        source="log",
        service=event.service,
        timestamp_start=event.timestamp,
        timestamp_end=window_end,
        observation=observation_from_log(event),
        raw_reference=event.raw_reference or f"log:{event.service}:{event.timestamp.isoformat()}",
    )


def evidence_from_deployment(
    deployment: Deployment,
    *,
    investigation_id: str,
    window_start: datetime,
    window_end: datetime,
) -> Evidence:
    return Evidence(
        evidence_id=_new_id("ev"),
        investigation_id=investigation_id,
        source="deployment",
        service=deployment.service,
        timestamp_start=deployment.deployed_at,
        timestamp_end=window_end,
        observation=observation_from_deployment(deployment),
        raw_reference=deployment.deployment_id,
    )


def evidence_from_trace(
    trace: TraceSummary,
    *,
    investigation_id: str,
    window_start: datetime,
    window_end: datetime,
) -> Evidence:
    occurred = trace.start_time or window_start
    return Evidence(
        evidence_id=_new_id("ev"),
        investigation_id=investigation_id,
        source="trace",
        service=trace.root_service,
        timestamp_start=occurred,
        timestamp_end=window_end,
        observation=observation_from_trace(trace),
        raw_reference=trace.trace_id,
    )


def timeline_from_evidence(evidence: Evidence) -> TimelineEvent:
    return TimelineEvent(
        event_id=_new_id("tl"),
        investigation_id=evidence.investigation_id or "",
        occurred_at=evidence.timestamp_start,
        summary=evidence.observation,
        evidence_id=evidence.evidence_id,
    )
