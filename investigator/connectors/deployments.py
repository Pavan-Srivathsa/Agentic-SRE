from __future__ import annotations

import json
import os
from datetime import datetime

import psycopg

from investigator.connectors.bounds import clamp_window
from investigator.models.telemetry import Deployment

INVESTIGATOR_DATABASE_URL = os.getenv(
    "INVESTIGATOR_DATABASE_URL",
    "postgresql://investigator:investigator@localhost:5433/investigator",
)


class DeploymentsClient:
    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or INVESTIGATOR_DATABASE_URL

    def get_recent_deployments(
        self,
        service: str,
        start: datetime,
        end: datetime,
    ) -> list[Deployment]:
        start, end = clamp_window(start, end)
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT deployment_id, service, version, commit_sha, deployed_at, metadata
                    FROM deployments
                    WHERE service = %s AND deployed_at >= %s AND deployed_at <= %s
                    ORDER BY deployed_at DESC
                    """,
                    (service, start, end),
                )
                rows = cur.fetchall()
        results: list[Deployment] = []
        for row in rows:
            metadata = row[5]
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            results.append(
                Deployment(
                    deployment_id=row[0],
                    service=row[1],
                    version=row[2],
                    commit_sha=row[3],
                    deployed_at=row[4],
                    metadata=metadata or {},
                )
            )
        return results
