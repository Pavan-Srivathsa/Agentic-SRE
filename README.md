# Agentic SRE

An incident diagnosis should be a **structured conclusion supported by observable evidence**, not an unsupported LLM answer.

This repository currently ships **Milestones 1–5**:

1. A reproducible checkout microservice environment with OpenTelemetry, Prometheus, Loki, Tempo, Grafana, and Alertmanager.
2. Typed, read-only connectors for metrics, logs, traces, deployments, and git — usable without an LLM.
3. Deterministic alert ingest, incident scoping, baseline evidence collection, and GET APIs for incident state, evidence, and timeline.
4. Investigator pipeline: hypothesis generation, verification, targeted evidence collection, and evidence-backed reports.
5. MCP server exposing the same connector and incident read tools over stdio.

The evaluation harness is **not** in this pass.

## Demo

```bash
docker compose up -d --build
make traffic
# wait ~30s for telemetry
make incident SCENARIO=bad-payment-deploy
```

Open Grafana at [http://localhost:3000](http://localhost:3000) (anonymous admin). Dashboard **Checkout** should show:

- api-gateway checkout p95 climbing above 2s
- payment-service / DB latency up
- inventory-service staying flat

Alert `HighCheckoutLatency` fires in Prometheus / Alertmanager after ~30s of SLO breach.

Walkthrough: [docs/demo.md](docs/demo.md)

## Investigator API (Milestones 3–4)

Start the API (requires investigator Postgres on `localhost:5433`):

```bash
pip install -e ".[dev]"
python -m investigator.api.app
```

Ingest a sample alert, run investigation + diagnosis:

```bash
make investigate
```

Endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/alerts` | Create alert + incident + investigation (`RECEIVED`) |
| `POST` | `/api/v1/incidents/{id}/investigate` | Scope, collect baseline, generate hypotheses, verify, report |
| `GET` | `/api/v1/incidents/{id}` | Incident status, scope, windows |
| `GET` | `/api/v1/incidents/{id}/evidence` | Evidence rows from connectors |
| `GET` | `/api/v1/incidents/{id}/timeline` | Programmatic timeline from evidence |
| `GET` | `/api/v1/incidents/{id}/hypotheses` | Ranked hypotheses with confidence |
| `GET` | `/api/v1/incidents/{id}/report` | Evidence-backed diagnosis report |

Status advances through `RECEIVED → SCOPING → BASELINE_COLLECTION → HYPOTHESIS_GENERATION → EVIDENCE_COLLECTION → VERIFICATION → DIAGNOSED → REPORT_GENERATED`.

Optional LLM hypothesis generation: set `OPENAI_API_KEY` (and `pip install -e ".[llm]"`). Without it, a deterministic rule-based generator is used.

## MCP Server (Milestone 5)

Expose investigation tools to MCP clients (Cursor, Claude Desktop, etc.):

```bash
pip install -e ".[mcp]"   # requires Python 3.10+
make mcp
```

Tools include `query_metrics`, `search_logs`, `find_slow_traces`, `get_recent_deployments`, `list_dependencies`, and incident read APIs. See [docs/mcp.md](docs/mcp.md) for Cursor configuration.

## Connectors

Semantic metric names are compiled to **validated PromQL templates**. Logs are capped at 30 minutes and 200 rows. Traces return a dependency tree, not a raw dump.

```bash
pip install -e ".[dev]"
python -m investigator.connectors.metrics --service payment-service --metric request_latency
```

## Make targets

```text
make up
make down
make traffic
make incident SCENARIO=bad-payment-deploy
make investigate
make mcp                 # stdio MCP server (Python 3.10+)
make mcp-smoke
make test
make test-integration   # requires compose + optional inject
```

## Architecture

```text
api-gateway → order-service → payment-service → postgres
                           ↘ inventory-service → postgres
```

Telemetry goes to an OpenTelemetry Collector, then Prometheus / Loki / Tempo. Investigator state lives in a **dedicated** Postgres (`localhost:5433`), not the checkout database.

## Not in this pass

- `make eval` / 15-scenario harness
- Write actions (restart, rollback, shell)
