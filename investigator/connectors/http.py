from __future__ import annotations

from typing import Any

import httpx

from investigator.connectors.bounds import DEFAULT_TIMEOUT_SECONDS, MAX_RETRIES


class ConnectorUnavailable(RuntimeError):
    def __init__(self, connector: str, message: str) -> None:
        super().__init__(message)
        self.connector = connector
        self.retryable = True


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    connector: str,
    params: dict[str, Any] | None = None,
) -> Any:
    last_error: Exception | None = None
    for _ in range(MAX_RETRIES + 1):
        try:
            response = await client.get(url, params=params, timeout=DEFAULT_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
    raise ConnectorUnavailable(connector, str(last_error)) from last_error
