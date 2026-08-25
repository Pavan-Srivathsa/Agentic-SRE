# Demo: payment deployment regression (INC-001)

Ground truth: `payment-service` v17 introduced an inefficient database query. The alert only names `api-gateway`.

## Start the stack

```bash
docker compose up -d --build
make traffic
```

Wait until `GET http://localhost:8000/health` returns ok and Grafana at http://localhost:3000 loads the **Checkout** dashboard.

## Inject the incident

```bash
make incident SCENARIO=bad-payment-deploy
```

This:

1. Enables slow-query mode on payment-service (`POST /admin/fault`).
2. Inserts a `payment-service` v17 row into investigator Postgres (`deployments`).
3. Leaves inventory-service unchanged.

## Diagnose in Grafana

1. Open **Checkout**.
2. Confirm gateway p95 rises above 2 seconds.
3. Confirm **payment** request and DB latency rise; **inventory** does not.
4. In Explore → Tempo, search `resource.service.name="payment-service"` and open a slow trace. Time should sit on payment → postgres, not inventory.
5. In Explore → Loki, query `{service_name="payment-service"} |= "timed out"`.
6. In Prometheus → Alerts, wait for `HighCheckoutLatency`.

## Investigator API (Milestones 3–4)

With Compose telemetry and investigator Postgres running:

```bash
pip install -e ".[dev]"
python -m investigator.api.app
```

In another terminal:

```bash
make investigate
```

Flow:

1. `POST /api/v1/alerts` with a `HighCheckoutLatency` alert for `api-gateway`.
2. `POST /api/v1/incidents/{id}/investigate` scopes dependencies, collects baseline evidence, generates hypotheses, verifies them, optionally collects targeted evidence, and produces a report.
3. `GET /api/v1/incidents/{id}/report` returns root cause, confidence, linked evidence IDs, timeline, and recommended action.

After `make incident`, the report should identify `payment-service` (deployment or database regression) with supporting deployment and latency evidence.

## Connector check (optional)

```bash
python -m investigator.connectors.metrics --service payment-service --metric database_latency
```

After inject, `get_recent_deployments` against `localhost:5433` should return version `v17` and commit `abc123def456`.
