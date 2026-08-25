from __future__ import annotations

import json
from pathlib import Path

from paths import SERVICE_GRAPH_PATH


def load_graph(path: Path | None = None) -> dict[str, list[str]]:
    source = path or SERVICE_GRAPH_PATH
    return json.loads(source.read_text(encoding="utf-8"))


def list_dependencies(service: str, depth: int = 1, graph: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    graph = graph or load_graph()
    levels: dict[str, list[str]] = {f"depth_{0}": [service]}
    seen = {service}
    frontier = [service]
    for current_depth in range(1, depth + 1):
        nxt: list[str] = []
        for node in frontier:
            for dep in graph.get(node, []):
                if dep not in seen:
                    seen.add(dep)
                    nxt.append(dep)
        levels[f"depth_{current_depth}"] = nxt
        frontier = nxt
    return levels
