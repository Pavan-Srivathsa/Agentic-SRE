from __future__ import annotations

from typing import Any

from investigator.connectors.bounds import MAX_LOG_RECORDS, MAX_TRACES
from investigator.connectors.dependencies import list_dependencies
from investigator.connectors.deployments import DeploymentsClient
from investigator.connectors.github import GitClient
from investigator.connectors.logs import LogsClient
from investigator.connectors.metrics import MetricsClient
from investigator.connectors.traces import TracesClient, format_trace_tree
from investigator.mcp.helpers import parse_timestamp, serialize_model, serialize_models
from investigator.storage.memory import MemoryStore
from investigator.storage.postgres import PostgresStore

METRIC_NAMES = (
    "request_rate",
    "error_rate",
    "request_latency",
    "cpu",
    "memory",
    "database_latency",
    "connection_pool_utilization",
    "queue_depth",
    "dependency_latency",
)


class ToolContext:
    def __init__(
        self,
        metrics: MetricsClient | None = None,
        logs: LogsClient | None = None,
        traces: TracesClient | None = None,
        deployments: DeploymentsClient | None = None,
        git: GitClient | None = None,
        store=None,
    ) -> None:
        self.metrics = metrics or MetricsClient()
        self.logs = logs or LogsClient()
        self.traces = traces or TracesClient()
        self.deployments = deployments or DeploymentsClient()
        self.git = git or GitClient()
        self.store = store


def create_default_context() -> ToolContext:
    import os

    if os.getenv("INVESTIGATOR_USE_MEMORY", "").lower() in {"1", "true", "yes"}:
        store = MemoryStore()
        store.seed_dependencies()
        return ToolContext(store=store)
    try:
        store = PostgresStore()
        store.run_migrations()
        store.seed_dependencies()
        return ToolContext(store=store)
    except Exception:
        return ToolContext(store=MemoryStore())


async def query_metrics(
    ctx: ToolContext,
    *,
    service: str,
    metric: str,
    start: str,
    end: str,
    aggregation: str = "p95",
) -> dict[str, Any]:
    if metric not in METRIC_NAMES:
        raise ValueError(f"unknown metric {metric!r}; expected one of {METRIC_NAMES}")
    series = await ctx.metrics.query_metrics(
        service,
        metric,
        parse_timestamp(start),
        parse_timestamp(end),
        aggregation=aggregation,
    )
    return serialize_model(series)


async def search_logs(
    ctx: ToolContext,
    *,
    service: str,
    start: str,
    end: str,
    level: str | None = None,
    pattern: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if limit > MAX_LOG_RECORDS:
        raise ValueError(f"limit exceeds {MAX_LOG_RECORDS}")
    events = await ctx.logs.search(
        service,
        parse_timestamp(start),
        parse_timestamp(end),
        level=level,
        pattern=pattern,
        limit=limit,
    )
    return {"events": serialize_models(events), "count": len(events)}


async def find_slow_traces(
    ctx: ToolContext,
    *,
    service: str,
    start: str,
    end: str,
    min_duration: str = "1s",
    limit: int = 10,
) -> dict[str, Any]:
    if limit > MAX_TRACES:
        raise ValueError(f"limit exceeds {MAX_TRACES}")
    traces = await ctx.traces.find_slow_traces(
        service,
        parse_timestamp(start),
        parse_timestamp(end),
        min_duration=min_duration,
        limit=limit,
    )
    return {"traces": serialize_models(traces), "count": len(traces)}


async def get_trace(ctx: ToolContext, *, trace_id: str) -> dict[str, Any]:
    tree = await ctx.traces.get_trace(trace_id)
    return {
        "trace": serialize_model(tree),
        "tree": format_trace_tree(tree),
    }


def get_recent_deployments(
    ctx: ToolContext,
    *,
    service: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    rows = ctx.deployments.get_recent_deployments(
        service,
        parse_timestamp(start),
        parse_timestamp(end),
    )
    return {"deployments": serialize_models(rows), "count": len(rows)}


def get_commit_diff(
    ctx: ToolContext,
    *,
    service: str,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    diff = ctx.git.get_commit_diff(service, commit_sha)
    return serialize_model(diff)


def list_service_dependencies(
    ctx: ToolContext,
    *,
    service: str,
    depth: int = 2,
) -> dict[str, Any]:
    levels = list_dependencies(service, depth=depth)
    return {"service": service, "depth": depth, "levels": levels}


def get_incident(ctx: ToolContext, *, incident_id: str) -> dict[str, Any]:
    if ctx.store is None:
        raise RuntimeError("incident store is not configured")
    incident = ctx.store.get_incident(incident_id)
    if incident is None:
        raise KeyError(f"incident not found: {incident_id}")
    return serialize_model(incident)


def get_incident_evidence(ctx: ToolContext, *, incident_id: str) -> dict[str, Any]:
    if ctx.store is None:
        raise RuntimeError("incident store is not configured")
    investigation = ctx.store.get_investigation_for_incident(incident_id)
    if investigation is None:
        raise KeyError(f"incident not found: {incident_id}")
    evidence = ctx.store.list_evidence(investigation.investigation_id)
    return {"evidence": serialize_models(evidence), "count": len(evidence)}


def get_incident_timeline(ctx: ToolContext, *, incident_id: str) -> dict[str, Any]:
    if ctx.store is None:
        raise RuntimeError("incident store is not configured")
    investigation = ctx.store.get_investigation_for_incident(incident_id)
    if investigation is None:
        raise KeyError(f"incident not found: {incident_id}")
    timeline = ctx.store.list_timeline(investigation.investigation_id)
    return {"timeline": serialize_models(timeline), "count": len(timeline)}


def get_incident_hypotheses(ctx: ToolContext, *, incident_id: str) -> dict[str, Any]:
    if ctx.store is None:
        raise RuntimeError("incident store is not configured")
    investigation = ctx.store.get_investigation_for_incident(incident_id)
    if investigation is None:
        raise KeyError(f"incident not found: {incident_id}")
    hypotheses = ctx.store.list_hypotheses(investigation.investigation_id)
    return {"hypotheses": serialize_models(hypotheses), "count": len(hypotheses)}


def get_incident_report(ctx: ToolContext, *, incident_id: str) -> dict[str, Any]:
    if ctx.store is None:
        raise RuntimeError("incident store is not configured")
    report = ctx.store.get_report_for_incident(incident_id)
    if report is None:
        raise KeyError(f"report not found for incident: {incident_id}")
    return serialize_model(report)
