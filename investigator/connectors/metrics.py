from __future__ import annotations

import os
from datetime import datetime

import httpx

from investigator.connectors.bounds import clamp_window, to_rfc3339
from investigator.connectors.http import get_json
from investigator.models.telemetry import MetricName, MetricPoint, MetricSeries

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")

TEMPLATES: dict[str, str] = {
    "request_rate": 'sum(rate(http_requests_total{{service="{service}"}}[1m]))',
    "error_rate": 'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[1m]))',
    "request_latency": (
        'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{service="{service}"}}[1m])))'
    ),
    "database_latency": (
        'histogram_quantile(0.95, sum by (le) (rate(db_query_duration_seconds_bucket{{service="{service}"}}[1m])))'
    ),
    "dependency_latency": (
        'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{service="{service}"}}[1m])))'
    ),
    "cpu": 'process_cpu_seconds_total{{service="{service}"}}',
    "memory": 'process_resident_memory_bytes{{service="{service}"}}',
    "connection_pool_utilization": 'db_query_duration_seconds_count{{service="{service}"}}',
    "queue_depth": 'http_requests_total{{service="{service}"}}',
}


def render_promql(service: str, metric: MetricName, aggregation: str = "p95") -> str:
    if metric not in TEMPLATES:
        raise KeyError(f"unknown metric: {metric}")
    query = TEMPLATES[metric].format(service=service)
    if metric in {"request_latency", "database_latency", "dependency_latency"} and aggregation == "p50":
        return query.replace("histogram_quantile(0.95", "histogram_quantile(0.50")
    return query


class MetricsClient:
    def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = (base_url or PROMETHEUS_URL).rstrip("/")
        self._client = client

    async def query_range(
        self,
        expression: str,
        start: datetime,
        end: datetime,
        step: str = "15s",
        *,
        service: str = "",
        metric: str = "",
        aggregation: str = "p95",
    ) -> MetricSeries:
        start, end = clamp_window(start, end)
        own = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            payload = await get_json(
                client,
                f"{self.base_url}/api/v1/query_range",
                connector="metrics",
                params={
                    "query": expression,
                    "start": to_rfc3339(start),
                    "end": to_rfc3339(end),
                    "step": step,
                },
            )
        finally:
            if own:
                await client.aclose()
        points: list[MetricPoint] = []
        for series in payload.get("data", {}).get("result", []):
            for ts, value in series.get("values", []):
                points.append(MetricPoint(timestamp=datetime.fromtimestamp(float(ts)), value=float(value)))
        return MetricSeries(
            metric=metric or expression,
            service=service,
            aggregation=aggregation,
            points=points,
            query=expression,
        )

    async def query_metrics(
        self,
        service: str,
        metric: MetricName,
        start: datetime,
        end: datetime,
        aggregation: str = "p95",
        step: str = "15s",
    ) -> MetricSeries:
        expression = render_promql(service, metric, aggregation)
        return await self.query_range(
            expression,
            start,
            end,
            step,
            service=service,
            metric=metric,
            aggregation=aggregation,
        )


async def main() -> None:
    import argparse
    from datetime import timedelta

    from investigator.connectors.bounds import utcnow

    parser = argparse.ArgumentParser()
    parser.add_argument("--service", default="api-gateway")
    parser.add_argument("--metric", default="request_latency")
    args = parser.parse_args()
    end = utcnow()
    series = await MetricsClient().query_metrics(args.service, args.metric, end - timedelta(minutes=10), end)
    print(series.model_dump_json(indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
