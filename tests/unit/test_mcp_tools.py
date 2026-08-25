from __future__ import annotations

from datetime import datetime, timezone

import pytest

from investigator.mcp.helpers import parse_timestamp
from investigator.mcp.tools import (
    ToolContext,
    get_commit_diff,
    get_incident,
    get_incident_report,
    get_recent_deployments,
    list_service_dependencies,
    query_metrics,
)
from investigator.models.incident import AlertIngest, IncidentStatus
from investigator.models.telemetry import CommitDiff
from investigator.storage.memory import MemoryStore
from tests.helpers.fakes import FakeDeployments, FakeMetrics


class FakeGit:
    def get_commit_diff(self, service: str, commit_sha: str | None = None) -> CommitDiff:
        return CommitDiff(
            commit_sha=commit_sha or "abc123def456",
            service=service,
            author="dev",
            message="optimize payment query",
            committed_at=datetime(2026, 8, 25, 15, 45, tzinfo=timezone.utc),
            files_changed=["payments/db.py"],
            diff_summary="added expensive join",
        )


@pytest.mark.asyncio
async def test_query_metrics_tool() -> None:
    ctx = ToolContext(metrics=FakeMetrics())
    result = await query_metrics(
        ctx,
        service="payment-service",
        metric="request_latency",
        start="2026-08-25T15:55:00Z",
        end="2026-08-25T16:10:00Z",
    )
    assert result["service"] == "payment-service"
    assert result["metric"] == "request_latency"


def test_list_dependencies_tool() -> None:
    ctx = ToolContext()
    result = list_service_dependencies(ctx, service="api-gateway", depth=2)
    assert "order-service" in result["levels"]["depth_1"]


def test_get_recent_deployments_tool() -> None:
    ctx = ToolContext(deployments=FakeDeployments())
    result = get_recent_deployments(
        ctx,
        service="payment-service",
        start="2026-08-25T15:30:00Z",
        end="2026-08-25T16:10:00Z",
    )
    assert result["count"] == 1
    assert result["deployments"][0]["version"] == "v17"


def test_get_commit_diff_tool() -> None:
    ctx = ToolContext(git=FakeGit())
    result = get_commit_diff(ctx, service="payment-service", commit_sha="abc123def456")
    assert result["service"] == "payment-service"
    assert "optimize payment query" in result["message"]


def test_incident_read_tools() -> None:
    store = MemoryStore()
    incident = store.ingest_alert(
        AlertIngest(
            alert_id="alert-mcp",
            alert_name="HighCheckoutLatency",
            service="api-gateway",
            severity="critical",
            starts_at=datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc),
        )
    )
    ctx = ToolContext(store=store)
    payload = get_incident(ctx, incident_id=incident.incident_id)
    assert payload["status"] == IncidentStatus.RECEIVED.value

    with pytest.raises(KeyError):
        get_incident_report(ctx, incident_id=incident.incident_id)


def test_parse_timestamp_accepts_zulu() -> None:
    parsed = parse_timestamp("2026-08-25T16:00:00Z")
    assert parsed.tzinfo is not None
    assert parsed.hour == 16
