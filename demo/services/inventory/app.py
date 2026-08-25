from __future__ import annotations

import os
import time

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from demo.services.shared.telemetry import DB_LATENCY, instrument_app, setup_logging, setup_otel

SERVICE = "inventory-service"
DATABASE_URL = os.getenv("APP_DATABASE_URL", "postgresql://checkout:checkout@postgres-app:5432/checkout")

logger = setup_logging(SERVICE)
setup_otel(SERVICE)
app = FastAPI(title=SERVICE)
instrument_app(app, SERVICE)


class ReserveRequest(BaseModel):
    order_id: str
    sku: str


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, connect_timeout=5)


@app.post("/reserve")
def reserve(body: ReserveRequest) -> dict:
    started = time.perf_counter()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE sku = %s", (body.sku,))
            row = cur.fetchone()
            if not row or row[0] <= 0:
                logger.error("sku unavailable sku=%s order_id=%s", body.sku, body.order_id)
                raise HTTPException(status_code=409, detail="out of stock")
            cur.execute("UPDATE inventory SET quantity = quantity - 1 WHERE sku = %s", (body.sku,))
            conn.commit()
    DB_LATENCY.labels(SERVICE, "reserve").observe(time.perf_counter() - started)
    logger.info("reserved sku=%s order_id=%s", body.sku, body.order_id)
    return {"ok": True, "sku": body.sku, "order_id": body.order_id}
