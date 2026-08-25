from datetime import datetime, timedelta, timezone

import httpx
import pytest

from investigator.connectors.metrics import MetricsClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_metrics_against_prometheus() -> None:
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=5)
    try:
        async with httpx.AsyncClient(timeout=2.0) as probe:
            response = await probe.get("http://localhost:9090/-/ready")
            response.raise_for_status()
    except Exception:
        pytest.skip("prometheus is not running")
    series = await MetricsClient().query_metrics("api-gateway", "request_rate", start, end)
    assert series.query
    assert series.service == "api-gateway"


@pytest.mark.integration
def test_deployments_after_inject() -> None:
    try:
        import psycopg
    except ImportError:
        pytest.skip("psycopg missing")
    try:
        conn = psycopg.connect(
            "postgresql://investigator:investigator@localhost:5433/investigator",
            connect_timeout=2,
        )
    except Exception:
        pytest.skip("investigator postgres is not running")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM deployments WHERE service = %s", ("payment-service",))
            count = cur.fetchone()[0]
    conn.close()
    if count == 0:
        pytest.skip("run make incident SCENARIO=bad-payment-deploy first")
    from investigator.connectors.deployments import DeploymentsClient

    rows = DeploymentsClient().get_recent_deployments(
        "payment-service",
        datetime.now(timezone.utc) - timedelta(minutes=30),
        datetime.now(timezone.utc),
    )
    assert rows
    assert rows[0].version == "v17"
