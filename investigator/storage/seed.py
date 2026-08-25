from __future__ import annotations

import json
from pathlib import Path

import psycopg

from investigator.connectors.dependencies import load_graph
from paths import SERVICE_GRAPH_PATH


def seed_service_dependencies(
    conn: psycopg.Connection,
    graph_path: Path | None = None,
) -> int:
    graph = load_graph(graph_path or SERVICE_GRAPH_PATH)
    rows = [(service, dependency) for service, deps in graph.items() for dependency in deps]
    with conn.cursor() as cur:
        for service, dependency in rows:
            cur.execute(
                """
                INSERT INTO service_dependencies (service, dependency)
                VALUES (%s, %s)
                ON CONFLICT (service, dependency) DO NOTHING
                """,
                (service, dependency),
            )
    conn.commit()
    return len(rows)


def seed_from_dsn(dsn: str, graph_path: Path | None = None) -> int:
    with psycopg.connect(dsn) as conn:
        return seed_service_dependencies(conn, graph_path)


def scope_to_json(scope) -> dict:
    return json.loads(scope.model_dump_json())


def scope_from_json(data: dict | None):
    if not data:
        return None
    from investigator.models.incident import Scope

    return Scope.model_validate(data)
