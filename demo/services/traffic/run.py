from __future__ import annotations

import asyncio
import os
import time

import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8000")
INTERVAL = float(os.getenv("TRAFFIC_INTERVAL_SECONDS", "1.0"))


async def main() -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            started = time.perf_counter()
            try:
                response = await client.post(
                    f"{GATEWAY_URL}/checkout",
                    json={"sku": "SKU-CHECKOUT", "amount_cents": 2599},
                )
                print(f"checkout {response.status_code} {time.perf_counter() - started:.3f}s", flush=True)
            except Exception as exc:
                print(f"checkout failed {exc}", flush=True)
            await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
