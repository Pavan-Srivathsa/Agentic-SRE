from __future__ import annotations

import os
import time
import uuid

import psycopg
from fastapi import FastAPI
from pydantic import BaseModel

from demo.services.shared.telemetry import DB_LATENCY, instrument_app, setup_logging, setup_otel

SERVICE = "payment-service"
DATABASE_URL = os.getenv("APP_DATABASE_URL", "postgresql://checkout:checkout@postgres-app:5432/checkout")

logger = setup_logging(SERVICE)
setup_otel(SERVICE)
app = FastAPI(title=SERVICE)
instrument_app(app, SERVICE)

_fault_enabled = False
_version = "v16"


class ChargeRequest(BaseModel):
    order_id: str
    amount_cents: int


class FaultRequest(BaseModel):
    enabled: bool
    version: str = "v17"


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, connect_timeout=5)


@app.post("/charge")
def charge(body: ChargeRequest) -> dict:
    payment_id = str(uuid.uuid4())
    started = time.perf_counter()
    with _connect() as conn:
        with conn.cursor() as cur:
            if _fault_enabled:
                logger.error(
                    "database request timed out order_id=%s payment_id=%s inefficient query in %s",
                    body.order_id,
                    payment_id,
                    _version,
                )
                cur.execute("SELECT pg_sleep(2.2)")
            cur.execute(
                "INSERT INTO payments (payment_id, amount_cents, status) VALUES (%s, %s, %s)",
                (payment_id, body.amount_cents, "captured"),
            )
            conn.commit()
    DB_LATENCY.labels(SERVICE, "charge").observe(time.perf_counter() - started)
    logger.info("charge captured payment_id=%s version=%s", payment_id, _version)
    return {"payment_id": payment_id, "status": "captured", "version": _version}


@app.post("/admin/fault")
def set_fault(body: FaultRequest) -> dict:
    global _fault_enabled, _version
    _fault_enabled = body.enabled
    _version = body.version
    logger.info("fault mode enabled=%s version=%s", _fault_enabled, _version)
    return {"enabled": _fault_enabled, "version": _version}


@app.get("/admin/fault")
def get_fault() -> dict:
    return {"enabled": _fault_enabled, "version": _version}
