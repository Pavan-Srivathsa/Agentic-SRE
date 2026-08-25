# MCP Server (Milestone 5)

The investigator exposes the same read-only connector and incident APIs as MCP tools over stdio.

**Requirements:** Python 3.10+ and `pip install -e ".[mcp]"`.

## Run locally

```bash
pip install -e ".[mcp]"
python -m investigator.mcp
```

The server uses stdio transport (for Cursor, Claude Desktop, and other MCP clients).

## Environment

Same variables as the REST API and connectors:

```text
PROMETHEUS_URL=http://localhost:9090
LOKI_URL=http://localhost:3100
TEMPO_URL=http://localhost:3200
INVESTIGATOR_DATABASE_URL=postgresql://investigator:investigator@localhost:5433/investigator
```

Set `INVESTIGATOR_USE_MEMORY=true` to use an in-memory store for incident read tools.

## Tools

| Tool | Description |
| --- | --- |
| `query_metrics` | Prometheus metrics for a service |
| `search_logs` | Loki log search |
| `find_slow_traces` | Tempo slow trace search |
| `get_trace` | Trace detail + dependency tree |
| `get_recent_deployments` | Deployment history from investigator Postgres |
| `get_commit_diff` | Changelog / commit metadata |
| `list_dependencies` | Service graph traversal |
| `get_incident` | Incident + investigation status |
| `get_incident_evidence` | Stored evidence rows |
| `get_incident_timeline` | Stored timeline events |
| `get_incident_hypotheses` | Ranked hypotheses |
| `get_incident_report` | Evidence-backed report |

All telemetry tools enforce the same bounds as the Python connectors (30-minute windows, row limits).

## Cursor configuration

Add to Cursor MCP settings (`.cursor/mcp.json` in the project or global settings):

```json
{
  "mcpServers": {
    "agentic-sre": {
      "command": "python3",
      "args": ["-m", "investigator.mcp"],
      "cwd": "/Users/pavan/Projects/Agentic SRE",
      "env": {
        "PROMETHEUS_URL": "http://localhost:9090",
        "LOKI_URL": "http://localhost:3100",
        "TEMPO_URL": "http://localhost:3200",
        "INVESTIGATOR_DATABASE_URL": "postgresql://investigator:investigator@localhost:5433/investigator"
      }
    }
  }
}
```

Use Python 3.10+ on the `command` path if the default `python3` is 3.9.

## Smoke test (no MCP client)

Call tools directly:

```bash
python scripts/mcp_smoke.py
```
