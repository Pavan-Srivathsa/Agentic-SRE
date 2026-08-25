from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import httpx

from investigator.connectors.bounds import MAX_TRACES, BoundsError, clamp_window
from investigator.connectors.http import get_json
from investigator.models.telemetry import SpanNode, TraceSummary, TraceTree

TEMPO_URL = os.getenv("TEMPO_URL", "http://localhost:3200")


def _attr_map(attributes: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in attributes or []:
        key = item.get("key")
        value = item.get("value", {})
        if not key:
            continue
        out[key] = next(iter(value.values()), "") if isinstance(value, dict) else str(value)
    return out


def parse_trace_payload(payload: dict, trace_id: str) -> TraceTree:
    batches = payload.get("batches") or payload.get("resourceSpans") or []
    spans: list[tuple[str, str, str, str, float]] = []
    services: set[str] = set()
    for batch in batches:
        resource = _attr_map((batch.get("resource") or {}).get("attributes") or [])
        service = resource.get("service.name", "unknown")
        services.add(service)
        for scope in batch.get("scopeSpans") or batch.get("instrumentationLibrarySpans") or []:
            for span in scope.get("spans") or []:
                start = int(span.get("startTimeUnixNano") or 0)
                end = int(span.get("endTimeUnixNano") or 0)
                duration_ms = (end - start) / 1_000_000 if end >= start else 0.0
                span_id = span.get("spanId") or ""
                parent = span.get("parentSpanId") or ""
                name = span.get("name") or "span"
                spans.append((span_id, parent, name, service, duration_ms))
    by_id = {
        span_id: SpanNode(span_id=span_id, name=name, service=service, duration_ms=duration_ms)
        for span_id, _, name, service, duration_ms in spans
    }
    roots: list[SpanNode] = []
    for span_id, parent, _, _, _ in spans:
        node = by_id[span_id]
        if parent and parent in by_id:
            by_id[parent].children.append(node)
        else:
            roots.append(node)
    root = roots[0] if roots else None
    duration = max((node.duration_ms for node in by_id.values()), default=0.0)
    return TraceTree(trace_id=trace_id, duration_ms=duration, root=root, services=sorted(services))


def format_trace_tree(tree: TraceTree) -> str:
    if tree.root is None:
        return f"{tree.trace_id} {tree.duration_ms:.0f}ms"

    def walk(node: SpanNode, indent: int) -> list[str]:
        prefix = "    " * indent + ("└── " if indent else "")
        lines = [f"{prefix}{node.service:20} {node.duration_ms:.0f}ms"]
        for child in node.children:
            lines.extend(walk(child, indent + 1))
        return lines

    return "\n".join(walk(tree.root, 0))


class TracesClient:
    def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = (base_url or TEMPO_URL).rstrip("/")
        self._client = client

    async def find_slow_traces(
        self,
        service: str,
        start: datetime,
        end: datetime,
        min_duration: str = "1s",
        limit: int = 10,
    ) -> list[TraceSummary]:
        start, end = clamp_window(start, end)
        if limit > MAX_TRACES:
            raise BoundsError(f"limit exceeds {MAX_TRACES}")
        query = f'{{resource.service.name="{service}" && duration>{min_duration}}}'
        own = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            payload = await get_json(
                client,
                f"{self.base_url}/api/search",
                connector="traces",
                params={
                    "q": query,
                    "limit": str(limit),
                    "start": str(int(start.timestamp())),
                    "end": str(int(end.timestamp())),
                },
            )
        finally:
            if own:
                await client.aclose()
        traces: list[TraceSummary] = []
        for item in payload.get("traces", []):
            start_ms = item.get("startTimeUnixNano")
            traces.append(
                TraceSummary(
                    trace_id=item.get("traceID") or item.get("traceId") or "",
                    root_service=item.get("rootServiceName") or service,
                    duration_ms=float(item.get("durationMs") or 0),
                    start_time=(
                        datetime.fromtimestamp(int(start_ms) / 1_000_000_000, tz=timezone.utc) if start_ms else None
                    ),
                )
            )
        return traces

    async def get_trace(self, trace_id: str) -> TraceTree:
        own = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            payload = await get_json(
                client,
                f"{self.base_url}/api/traces/{trace_id}",
                connector="traces",
            )
        finally:
            if own:
                await client.aclose()
        if isinstance(payload, str):
            payload = json.loads(payload)
        return parse_trace_payload(payload, trace_id)
