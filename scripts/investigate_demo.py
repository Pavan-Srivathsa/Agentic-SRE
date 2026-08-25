#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Post sample alert and run investigate flow.")
    parser.add_argument("--url", default="http://localhost:8080")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    payload = {
        "alert_id": "alert-demo-checkout",
        "alert_name": "HighCheckoutLatency",
        "service": "api-gateway",
        "severity": "critical",
        "starts_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "labels": {"team": "checkout"},
        "annotations": {"summary": "Checkout p95 above 2s"},
    }
    with httpx.Client(timeout=60.0) as client:
        alert_resp = client.post(f"{base}/api/v1/alerts", json=payload)
        alert_resp.raise_for_status()
        incident = alert_resp.json()["incident"]
        incident_id = incident["incident_id"]
        print(f"created incident {incident_id} status={incident['status']}")

        inv_resp = client.post(f"{base}/api/v1/incidents/{incident_id}/investigate")
        inv_resp.raise_for_status()
        investigated = inv_resp.json()["incident"]
        print(f"investigated status={investigated['status']}")

        report_resp = client.get(f"{base}/api/v1/incidents/{incident_id}/report")
        if report_resp.status_code == 200:
            report = report_resp.json()["report"]
            print(f"root cause: {report['root_cause']}")
            print(f"confidence: {report['confidence']}")
            print(f"recommended action: {report['recommended_action']}")
            print()
            print(report["body"])
        else:
            print("report not available yet")

        print(json.dumps({"incident_id": incident_id, "status": investigated["status"]}, indent=2))


if __name__ == "__main__":
    main()
