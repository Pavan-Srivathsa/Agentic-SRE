from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import yaml

ROOT = Path(__file__).resolve().parents[2]
PAYMENT_URL = "http://localhost:8002"
INVESTIGATOR_DSN = "postgresql://investigator:investigator@localhost:5433/investigator"
CHANGELOG = ROOT / "demo" / "changelog" / "commits.json"
SCENARIOS = ROOT / "evals" / "scenarios"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def inject_bad_payment_deploy() -> None:
    scenario = yaml.safe_load((SCENARIOS / "INC-001.yaml").read_text(encoding="utf-8"))
    commit = next(c for c in json.loads(CHANGELOG.read_text(encoding="utf-8")) if c["service"] == "payment-service")
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{PAYMENT_URL}/admin/fault",
            json={"enabled": True, "version": "v17"},
        )
        response.raise_for_status()
    deployment_id = f"deploy-{uuid4().hex[:8]}"
    with psycopg.connect(INVESTIGATOR_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO deployments (deployment_id, service, version, commit_sha, deployed_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    deployment_id,
                    "payment-service",
                    "v17",
                    commit["commit_sha"],
                    _utcnow(),
                    json.dumps({"scenario": scenario["incident_id"]}),
                ),
            )
            conn.commit()
    print(f"Injected {scenario['incident_id']}: payment-service v17 ({deployment_id})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="bad-payment-deploy")
    args = parser.parse_args()
    if args.scenario != "bad-payment-deploy":
        raise SystemExit(f"unknown scenario: {args.scenario}")
    inject_bad_payment_deploy()


if __name__ == "__main__":
    main()
