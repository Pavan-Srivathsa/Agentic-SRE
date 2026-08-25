from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from investigator.connectors.bounds import MAX_LOG_RECORDS, BoundsError, clamp_window, to_unix_nanos
from investigator.connectors.http import get_json
from investigator.models.telemetry import LogEvent

LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")


class LogsClient:
    def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = (base_url or LOKI_URL).rstrip("/")
        self._client = client

    async def search(
        self,
        service: str,
        start: datetime,
        end: datetime,
        level: str | None = None,
        pattern: str | None = None,
        limit: int = MAX_LOG_RECORDS,
    ) -> list[LogEvent]:
        start, end = clamp_window(start, end)
        if limit > MAX_LOG_RECORDS:
            raise BoundsError(f"limit exceeds {MAX_LOG_RECORDS}")
        query = f'{{service_name="{service}"}}'
        if level:
            query += f' |= "{level}"'
        if pattern:
            query += f' |= "{pattern}"'
        own = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            payload = await get_json(
                client,
                f"{self.base_url}/loki/api/v1/query_range",
                connector="logs",
                params={
                    "query": query,
                    "start": str(to_unix_nanos(start)),
                    "end": str(to_unix_nanos(end)),
                    "limit": str(limit),
                    "direction": "backward",
                },
            )
        finally:
            if own:
                await client.aclose()
        events: list[LogEvent] = []
        for stream in payload.get("data", {}).get("result", []):
            labels = stream.get("stream", {})
            svc = labels.get("service_name") or labels.get("service") or service
            for ts, line in stream.get("values", []):
                seconds = int(ts) / 1_000_000_000
                events.append(
                    LogEvent(
                        timestamp=datetime.fromtimestamp(seconds, tz=timezone.utc),
                        service=svc,
                        severity=level or "INFO",
                        message=line,
                        raw_reference=f"loki:{svc}:{ts}",
                    )
                )
        return events[:limit]
