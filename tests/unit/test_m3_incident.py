from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from investigator.models.evidence import TimelineEvent
from investigator.models.incident import AlertIngest, IncidentStatus
from investigator.models.telemetry import Deployment, LogEvent, MetricPoint, MetricSeries
from investigator.orchestration.evidence_mapping import (
    evidence_from_deployment,
    evidence_from_log,
    observation_from_metric,
    timeline_from_evidence,
)
from investigator.orchestration.scoping import baseline_window, build_scope, incident_window
from investigator.orchestration.state_machine import InvalidTransition, transition


def test_alert_ingest_requires_fields() -> None:
    with pytest.raises(ValidationError):
        AlertIngest.model_validate({"alert_id": "a1"})


def test_incident_window_offsets() -> None:
    starts_at = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    window = incident_window(starts_at)
    assert window.start == datetime(2026, 8, 25, 15, 55, tzinfo=timezone.utc)
    assert window.end == datetime(2026, 8, 25, 16, 10, tzinfo=timezone.utc)


def test_baseline_window_before_incident() -> None:
    starts_at = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    incident = incident_window(starts_at)
    baseline = baseline_window(incident)
    assert baseline.end == incident.start
    assert (baseline.end - baseline.start).total_seconds() == 25 * 60


def test_build_scope_depth_two() -> None:
    alert = AlertIngest(
        alert_id="alert-1",
        alert_name="HighCheckoutLatency",
        service="api-gateway",
        severity="critical",
        starts_at=datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc),
    )
    scope = build_scope(alert, depth=2)
    assert scope.primary_service == "api-gateway"
    assert "order-service" in scope.services
    assert "payment-service" in scope.services


def test_illegal_state_transition() -> None:
    with pytest.raises(InvalidTransition):
        transition(IncidentStatus.RECEIVED, IncidentStatus.BASELINE_COLLECTION)


def test_legal_received_to_scoping() -> None:
    assert transition(IncidentStatus.RECEIVED, IncidentStatus.SCOPING) == IncidentStatus.SCOPING


def test_metric_observation_last_point() -> None:
    ts = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    series = MetricSeries(
        metric="request_latency",
        service="api-gateway",
        aggregation="p95",
        points=[MetricPoint(timestamp=ts, value=2.5)],
        query="histogram_quantile(...)",
    )
    assert "2.5000" in observation_from_metric(series)


def test_evidence_mapping_from_log() -> None:
    ts = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    event = LogEvent(
        timestamp=ts,
        service="payment-service",
        severity="ERROR",
        message="query timed out",
        raw_reference="loki:payment-service:1",
    )
    evidence = evidence_from_log(event, investigation_id="inv-1", window_end=ts)
    assert evidence.source == "log"
    assert "timed out" in evidence.observation


def test_timeline_sorted_by_occurred_at() -> None:
    early = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)
    late = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    events = [
        TimelineEvent(event_id="b", investigation_id="inv", occurred_at=late, summary="later"),
        TimelineEvent(event_id="a", investigation_id="inv", occurred_at=early, summary="earlier"),
    ]
    ordered = sorted(events, key=lambda item: (item.occurred_at, item.event_id))
    assert ordered[0].summary == "earlier"


def test_deployment_evidence_sentence() -> None:
    deployed_at = datetime(2026, 8, 25, 15, 30, tzinfo=timezone.utc)
    deployment = Deployment(
        deployment_id="dep-1",
        service="payment-service",
        version="v17",
        commit_sha="abc123def456",
        deployed_at=deployed_at,
    )
    evidence = evidence_from_deployment(
        deployment,
        investigation_id="inv-1",
        window_start=deployed_at,
        window_end=deployed_at,
    )
    assert "v17" in evidence.observation
    timeline = timeline_from_evidence(evidence)
    assert timeline.evidence_id == evidence.evidence_id
