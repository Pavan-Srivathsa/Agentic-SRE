from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from demo.services.shared.telemetry import instrument_app, setup_logging, setup_otel

SERVICE = "api-gateway"
ORDER_URL = os.getenv("ORDER_URL", "http://orders:8001")

logger = setup_logging(SERVICE)
setup_otel(SERVICE)
app = FastAPI(title=SERVICE)
instrument_app(app, SERVICE)


class CheckoutRequest(BaseModel):
    sku: str = "SKU-CHECKOUT"
    amount_cents: int = 2599


@app.post("/checkout")
async def checkout(body: CheckoutRequest) -> dict:
    logger.info("checkout started sku=%s amount_cents=%s", body.sku, body.amount_cents)
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(
            f"{ORDER_URL}/orders",
            json={"sku": body.sku, "amount_cents": body.amount_cents},
        )
    if response.status_code >= 400:
        logger.error("checkout failed status=%s body=%s", response.status_code, response.text)
        raise HTTPException(status_code=502, detail="order-service failed")
    payload = response.json()
    logger.info("checkout completed order_id=%s", payload.get("order_id"))
    return {"ok": True, "order": payload}
