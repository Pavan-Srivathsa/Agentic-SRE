from __future__ import annotations

from investigator.models.telemetry import Deployment, LogEvent, MetricPoint, MetricSeries, TraceSummary


class FakeMetrics:
    async def query_metrics(self, service, metric, start, end, aggregation="p95", step="15s"):
        if metric == "database_latency":
            value = 2.5 if service == "payment-service" else 0.15
        elif service == "inventory-service":
            value = 0.2
        else:
            value = 1.23
        return MetricSeries(
            metric=metric,
            service=service,
            aggregation=aggregation,
            points=[MetricPoint(timestamp=start, value=value)],
            query=f"fake:{metric}",
        )


class FakeLogs:
    async def search(self, service, start, end, level=None, pattern=None, limit=200):
        return [
            LogEvent(
                timestamp=start,
                service=service,
                severity=level or "ERROR",
                message="synthetic error",
                raw_reference=f"fake:{service}",
            )
        ]


class FakeTraces:
    async def find_slow_traces(self, service, start, end, min_duration="1s", limit=10):
        return [
            TraceSummary(
                trace_id="trace-abc123",
                root_service=service,
                duration_ms=2500.0,
                start_time=start,
            )
        ]


class FakeDeployments:
    def get_recent_deployments(self, service, start, end):
        if service == "payment-service":
            return [
                Deployment(
                    deployment_id="dep-v17",
                    service=service,
                    version="v17",
                    commit_sha="abc123def456",
                    deployed_at=start,
                )
            ]
        return []
