from __future__ import annotations

from datetime import datetime, timezone

import pytest

from investigator.models.incident import AlertIngest, IncidentStatus
from investigator.orchestration.baseline import BaselineCollector, CollectorBundle, run_investigation
from investigator.storage.memory import MemoryStore
from tests.helpers.fakes import FakeDeployments, FakeLogs, FakeMetrics, FakeTraces


@pytest.mark.asyncio
async def test_investigate_flow_memory_store() -> None:
    store = MemoryStore()
    starts_at = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    incident = store.ingest_alert(
        AlertIngest(
            alert_id="alert-test",
            alert_name="HighCheckoutLatency",
            service="api-gateway",
            severity="critical",
            starts_at=starts_at,
        )
    )
    collector = BaselineCollector(
        CollectorBundle(
            metrics=FakeMetrics(),
            logs=FakeLogs(),
            traces=FakeTraces(),
            deployments=FakeDeployments(),
        )
    )
    result = await run_investigation(store, incident.incident_id, collector=collector)
    assert result.status == IncidentStatus.REPORT_GENERATED
    assert result.scope is not None
    assert "payment-service" in result.scope.services

    investigation = store.get_investigation_for_incident(incident.incident_id)
    assert investigation is not None
    evidence = store.list_evidence(investigation.investigation_id)
    assert evidence
    assert any(item.service == "payment-service" and item.source == "deployment" for item in evidence)

    report = store.get_report_for_incident(incident.incident_id)
    assert report is not None
    assert report.root_service == "payment-service"

    timeline = store.list_timeline(investigation.investigation_id)
    assert len(timeline) == len(evidence)
    assert timeline == sorted(timeline, key=lambda item: (item.occurred_at, item.event_id))
