from __future__ import annotations

from investigator.mcp import tools as tool_impl


def run_stdio_server() -> None:
    from mcp.server.fastmcp import FastMCP

    ctx = tool_impl.create_default_context()
    mcp = FastMCP("agentic-sre-investigator")

    @mcp.tool()
    async def query_metrics(
        service: str,
        metric: str,
        start: str,
        end: str,
        aggregation: str = "p95",
    ) -> dict:
        """Query Prometheus metrics for a service within a bounded time window."""
        return await tool_impl.query_metrics(
            ctx,
            service=service,
            metric=metric,
            start=start,
            end=end,
            aggregation=aggregation,
        )

    @mcp.tool()
    async def search_logs(
        service: str,
        start: str,
        end: str,
        level: str | None = None,
        pattern: str | None = None,
        limit: int = 50,
    ) -> dict:
        """Search Loki logs for a service within a bounded time window."""
        return await tool_impl.search_logs(
            ctx,
            service=service,
            start=start,
            end=end,
            level=level,
            pattern=pattern,
            limit=limit,
        )

    @mcp.tool()
    async def find_slow_traces(
        service: str,
        start: str,
        end: str,
        min_duration: str = "1s",
        limit: int = 10,
    ) -> dict:
        """Find slow distributed traces for a service in Tempo."""
        return await tool_impl.find_slow_traces(
            ctx,
            service=service,
            start=start,
            end=end,
            min_duration=min_duration,
            limit=limit,
        )

    @mcp.tool()
    async def get_trace(trace_id: str) -> dict:
        """Fetch a trace by ID and return a dependency tree summary."""
        return await tool_impl.get_trace(ctx, trace_id=trace_id)

    @mcp.tool()
    def get_recent_deployments(service: str, start: str, end: str) -> dict:
        """List recent deployments for a service from investigator Postgres."""
        return tool_impl.get_recent_deployments(ctx, service=service, start=start, end=end)

    @mcp.tool()
    def get_commit_diff(service: str, commit_sha: str | None = None) -> dict:
        """Fetch commit metadata and diff summary for a service deployment."""
        return tool_impl.get_commit_diff(ctx, service=service, commit_sha=commit_sha)

    @mcp.tool()
    def list_dependencies(service: str, depth: int = 2) -> dict:
        """Return downstream service dependencies up to the requested depth."""
        return tool_impl.list_service_dependencies(ctx, service=service, depth=depth)

    @mcp.tool()
    def get_incident(incident_id: str) -> dict:
        """Read a persisted incident and investigation status."""
        return tool_impl.get_incident(ctx, incident_id=incident_id)

    @mcp.tool()
    def get_incident_evidence(incident_id: str) -> dict:
        """List evidence rows collected for an incident."""
        return tool_impl.get_incident_evidence(ctx, incident_id=incident_id)

    @mcp.tool()
    def get_incident_timeline(incident_id: str) -> dict:
        """Return the programmatic timeline for an incident."""
        return tool_impl.get_incident_timeline(ctx, incident_id=incident_id)

    @mcp.tool()
    def get_incident_hypotheses(incident_id: str) -> dict:
        """Return ranked hypotheses for an incident investigation."""
        return tool_impl.get_incident_hypotheses(ctx, incident_id=incident_id)

    @mcp.tool()
    def get_incident_report(incident_id: str) -> dict:
        """Return the evidence-backed diagnosis report for an incident."""
        return tool_impl.get_incident_report(ctx, incident_id=incident_id)

    mcp.run()
