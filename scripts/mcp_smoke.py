#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json

from investigator.mcp.tools import ToolContext, list_service_dependencies, query_metrics


async def main() -> None:
    ctx = ToolContext()
    deps = list_service_dependencies(ctx, service="api-gateway", depth=2)
    print("dependencies:", json.dumps(deps, indent=2))
    try:
        metrics = await query_metrics(
            ctx,
            service="api-gateway",
            metric="request_rate",
            start="2026-08-25T15:55:00Z",
            end="2026-08-25T16:10:00Z",
        )
        print("metrics:", json.dumps(metrics, indent=2)[:500])
    except Exception as exc:
        print(f"metrics query skipped: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
