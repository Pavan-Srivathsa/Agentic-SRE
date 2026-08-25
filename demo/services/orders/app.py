from __future__ import annotations

import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from demo.services.shared.telemetry import instrument_app, setup_logging, setup_otel

SERVICE = "order-service"
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payments:8002")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://inventory:8003")

logger = setup_logging(SERVICE)
setup_otel(SERVICE)
app = FastAPI(title=SERVICE)
instrument_app(app, SERVICE)


class OrderRequest(BaseModel):
    sku: str
    amount_cents: int


@app.post("/orders")
async def create_order(body: OrderRequest) -> dict:
    order_id = str(uuid.uuid4())
    logger.info("order created order_id=%s sku=%s", order_id, body.sku)
    async with httpx.AsyncClient(timeout=8.0) as client:
        pay = await client.post(
            f"{PAYMENT_URL}/charge",
            json={"order_id": order_id, "amount_cents": body.amount_cents},
        )
        if pay.status_code >= 400:
            logger.error("payment failed order_id=%s status=%s", order_id, pay.status_code)
            raise HTTPException(status_code=502, detail="payment-service failed")
        inv = await client.post(
            f"{INVENTORY_URL}/reserve",
            json={"order_id": order_id, "sku": body.sku},
        )
        if inv.status_code >= 400:
            logger.error("inventory failed order_id=%s status=%s", order_id, inv.status_code)
            raise HTTPException(status_code=502, detail="inventory-service failed")
    return {
        "order_id": order_id,
        "payment": pay.json(),
        "inventory": inv.json(),
    }
