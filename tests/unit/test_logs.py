from datetime import datetime, timezone

import httpx
import pytest

from investigator.connectors.logs import LogsClient
from investigator.models.telemetry import LogEvent


@pytest.mark.asyncio
async def test_search_logs_parses_loki_payload() -> None:
    payload = {
        "data": {
            "result": [
                {
                    "stream": {"service_name": "payment-service"},
                    "values": [
                        ["1756137600000000000", "database request timed out order_id=1"],
                    ],
                }
            ]
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        events = await LogsClient(base_url="http://loki", client=client).search(
            "payment-service",
            datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 25, 16, 10, tzinfo=timezone.utc),
        )
    assert events
    assert isinstance(events[0], LogEvent)
    assert "timed out" in events[0].message
