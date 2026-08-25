from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from investigator.api.app import app
from investigator.orchestration.baseline import BaselineCollector, CollectorBundle, run_investigation
from investigator.storage.memory import MemoryStore
from tests.helpers.fakes import FakeDeployments, FakeLogs, FakeMetrics, FakeTraces


@pytest.fixture
def client(monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr("investigator.api.app.create_store", lambda: store)

    async def fake_run(store_arg, incident_id, collector=None):
        fake_collector = BaselineCollector(
            CollectorBundle(
                metrics=FakeMetrics(),
                logs=FakeLogs(),
                traces=FakeTraces(),
                deployments=FakeDeployments(),
            )
        )
        return await run_investigation(store_arg, incident_id, collector=fake_collector)

    monkeypatch.setattr("investigator.api.app.run_investigation", fake_run)
    with TestClient(app) as test_client:
        yield test_client, store


def test_alert_and_investigate_endpoints(client) -> None:
    test_client, _store = client
    payload = {
        "alert_id": "alert-api-test",
        "alert_name": "HighCheckoutLatency",
        "service": "api-gateway",
        "severity": "critical",
        "starts_at": datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "labels": {},
        "annotations": {},
    }
    created = test_client.post("/api/v1/alerts", json=payload)
    assert created.status_code == 200
    incident_id = created.json()["incident"]["incident_id"]

    investigated = test_client.post(f"/api/v1/incidents/{incident_id}/investigate")
    assert investigated.status_code == 200
    body = investigated.json()["incident"]
    assert body["status"] == "REPORT_GENERATED"
    assert body["scope"]["primary_service"] == "api-gateway"

    report = test_client.get(f"/api/v1/incidents/{incident_id}/report")
    assert report.status_code == 200
    assert report.json()["report"]["root_service"] == "payment-service"

    evidence = test_client.get(f"/api/v1/incidents/{incident_id}/evidence")
    assert evidence.status_code == 200

    timeline = test_client.get(f"/api/v1/incidents/{incident_id}/timeline")
    assert timeline.status_code == 200


@pytest.mark.integration
def test_postgres_investigate_payment_deployment_evidence() -> None:
    dsn = os.getenv(
        "INVESTIGATOR_DATABASE_URL",
        "postgresql://investigator:investigator@localhost:5433/investigator",
    )
    try:
        import psycopg

        conn = psycopg.connect(dsn, connect_timeout=2)
    except Exception:
        pytest.skip("investigator postgres is not running")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM deployments WHERE service = %s", ("payment-service",))
            if cur.fetchone()[0] == 0:
                pytest.skip("run make incident SCENARIO=bad-payment-deploy first")
    conn.close()

    api_url = os.getenv("INVESTIGATOR_URL", "http://localhost:8080")
    try:
        with httpx.Client(timeout=5.0) as probe:
            probe.get(f"{api_url}/docs")
    except Exception:
        pytest.skip("investigator API is not running")

    payload = {
        "alert_id": f"alert-int-{datetime.now(timezone.utc).timestamp()}",
        "alert_name": "HighCheckoutLatency",
        "service": "api-gateway",
        "severity": "critical",
        "starts_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "labels": {},
        "annotations": {},
    }
    with httpx.Client(timeout=60.0) as client:
        created = client.post(f"{api_url}/api/v1/alerts", json=payload)
        created.raise_for_status()
        incident_id = created.json()["incident"]["incident_id"]
        investigated = client.post(f"{api_url}/api/v1/incidents/{incident_id}/investigate")
        investigated.raise_for_status()
        evidence = client.get(f"{api_url}/api/v1/incidents/{incident_id}/evidence")
        evidence.raise_for_status()
    rows = evidence.json()["evidence"]
    assert any(row["service"] == "payment-service" and row["source"] == "deployment" for row in rows)
