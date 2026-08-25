from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEMO_DIR = ROOT / "demo"
OBSERVABILITY_DIR = DEMO_DIR / "observability"
CHANGELOG_PATH = DEMO_DIR / "changelog" / "commits.json"
SERVICE_GRAPH_PATH = OBSERVABILITY_DIR / "service-graph.json"
SCENARIOS_DIR = ROOT / "evals" / "scenarios"
MIGRATIONS_DIR = ROOT / "investigator" / "storage" / "migrations"
