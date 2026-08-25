from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from investigator.models.evidence import Evidence, TimelineEvent
from investigator.models.incident import (
    Alert,
    AlertIngest,
    Incident,
    IncidentStatus,
    Investigation,
    Transition,
)
from investigator.storage.seed import scope_from_json, scope_to_json, seed_service_dependencies
from paths import MIGRATIONS_DIR

INVESTIGATOR_DATABASE_URL = os.getenv(
    "INVESTIGATOR_DATABASE_URL",
    "postgresql://investigator:investigator@localhost:5433/investigator",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class PostgresStore:
    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or INVESTIGATOR_DATABASE_URL

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)

    def run_migrations(self, migrations_dir: Path | None = None) -> None:
        directory = migrations_dir or MIGRATIONS_DIR
        with self.connect() as conn:
            for path in sorted(directory.glob("*.sql")):
                sql = path.read_text(encoding="utf-8")
                with conn.cursor() as cur:
                    cur.execute(sql)
            conn.commit()

    def seed_dependencies(self) -> int:
        with self.connect() as conn:
            return seed_service_dependencies(conn)

    def ingest_alert(self, payload: AlertIngest) -> Incident:
        incident_id = _new_id("inc")
        investigation_id = _new_id("inv")
        now = _utcnow()
        alert_payload = {
            "labels": payload.labels,
            "annotations": payload.annotations,
        }
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO alerts (alert_id, alert_name, service, severity, starts_at, payload)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (alert_id) DO UPDATE SET
                        alert_name = EXCLUDED.alert_name,
                        service = EXCLUDED.service,
                        severity = EXCLUDED.severity,
                        starts_at = EXCLUDED.starts_at,
                        payload = EXCLUDED.payload
                    """,
                    (
                        payload.alert_id,
                        payload.alert_name,
                        payload.service,
                        payload.severity,
                        payload.starts_at,
                        json.dumps(alert_payload),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO incidents (incident_id, alert_id, service, severity, started_at, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        incident_id,
                        payload.alert_id,
                        payload.service,
                        payload.severity,
                        payload.starts_at,
                        IncidentStatus.RECEIVED.value,
                        now,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO investigations (investigation_id, incident_id, status, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (investigation_id, incident_id, IncidentStatus.RECEIVED.value, now),
                )
                self._record_transition(cur, investigation_id, None, IncidentStatus.RECEIVED, now)
            conn.commit()
        return Incident(
            incident_id=incident_id,
            alert_id=payload.alert_id,
            service=payload.service,
            severity=payload.severity,
            started_at=payload.starts_at,
            status=IncidentStatus.RECEIVED,
            created_at=now,
            investigation_id=investigation_id,
        )

    def get_incident(self, incident_id: str) -> Incident | None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT i.incident_id, i.alert_id, i.service, i.severity, i.started_at, i.status, i.created_at,
                           inv.investigation_id, inv.scope, inv.notes
                    FROM incidents i
                    LEFT JOIN investigations inv ON inv.incident_id = i.incident_id
                    WHERE i.incident_id = %s
                    ORDER BY inv.created_at DESC
                    LIMIT 1
                    """,
                    (incident_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return self._incident_from_row(row)

    def get_investigation(self, investigation_id: str) -> Investigation | None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT investigation_id, incident_id, status, created_at, scope, notes
                    FROM investigations
                    WHERE investigation_id = %s
                    """,
                    (investigation_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return self._investigation_from_row(row)

    def get_investigation_for_incident(self, incident_id: str) -> Investigation | None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT investigation_id, incident_id, status, created_at, scope, notes
                    FROM investigations
                    WHERE incident_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (incident_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return self._investigation_from_row(row)

    def advance_status(
        self,
        investigation_id: str,
        current: IncidentStatus,
        nxt: IncidentStatus,
        *,
        scope=None,
        notes: str | None = None,
        append_notes: str | None = None,
    ) -> Transition:
        now = _utcnow()
        with self.connect() as conn:
            with conn.cursor() as cur:
                if append_notes:
                    cur.execute(
                        "SELECT notes FROM investigations WHERE investigation_id = %s",
                        (investigation_id,),
                    )
                    existing = cur.fetchone()
                    prior = existing[0] if existing and existing[0] else ""
                    notes = f"{prior}\n{append_notes}".strip() if prior else append_notes
                updates = ["status = %s"]
                params: list = [nxt.value]
                if scope is not None:
                    updates.append("scope = %s::jsonb")
                    params.append(json.dumps(scope_to_json(scope)))
                if notes is not None:
                    updates.append("notes = %s")
                    params.append(notes)
                params.append(investigation_id)
                cur.execute(
                    f"UPDATE investigations SET {', '.join(updates)} WHERE investigation_id = %s",
                    params,
                )
                cur.execute(
                    "UPDATE incidents SET status = %s WHERE incident_id = (SELECT incident_id FROM investigations WHERE investigation_id = %s)",
                    (nxt.value, investigation_id),
                )
                event = self._record_transition(cur, investigation_id, current, nxt, now)
            conn.commit()
        return event

    def add_evidence(self, evidence: Evidence) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO evidence (
                        evidence_id, investigation_id, source, service,
                        timestamp_start, timestamp_end, observation, raw_reference,
                        supports, contradicts
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        evidence.evidence_id,
                        evidence.investigation_id,
                        evidence.source,
                        evidence.service,
                        evidence.timestamp_start,
                        evidence.timestamp_end,
                        evidence.observation,
                        evidence.raw_reference,
                        evidence.supports,
                        evidence.contradicts,
                    ),
                )
            conn.commit()

    def list_evidence(self, investigation_id: str) -> list[Evidence]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT evidence_id, investigation_id, source, service,
                           timestamp_start, timestamp_end, observation, raw_reference,
                           supports, contradicts
                    FROM evidence
                    WHERE investigation_id = %s
                    ORDER BY timestamp_start ASC
                    """,
                    (investigation_id,),
                )
                rows = cur.fetchall()
        return [self._evidence_from_row(row) for row in rows]

    def add_timeline_event(self, event: TimelineEvent) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO timeline_events (event_id, investigation_id, occurred_at, summary, evidence_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        event.event_id,
                        event.investigation_id,
                        event.occurred_at,
                        event.summary,
                        event.evidence_id,
                    ),
                )
            conn.commit()

    def list_timeline(self, investigation_id: str) -> list[TimelineEvent]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id, investigation_id, occurred_at, summary, evidence_id
                    FROM timeline_events
                    WHERE investigation_id = %s
                    ORDER BY occurred_at ASC, event_id ASC
                    """,
                    (investigation_id,),
                )
                rows = cur.fetchall()
        return [self._timeline_from_row(row) for row in rows]

    def get_alert(self, alert_id: str) -> Alert | None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT alert_id, alert_name, service, severity, starts_at, payload
                    FROM alerts WHERE alert_id = %s
                    """,
                    (alert_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return Alert(
            alert_id=row[0],
            alert_name=row[1],
            service=row[2],
            severity=row[3],
            starts_at=row[4],
            payload=row[5] or {},
        )

    def replace_hypotheses(self, investigation_id: str, hypotheses) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM hypotheses WHERE investigation_id = %s", (investigation_id,))
                for item in hypotheses:
                    cur.execute(
                        """
                        INSERT INTO hypotheses (
                            hypothesis_id, investigation_id, title, description,
                            affected_service, confidence, status,
                            supporting_evidence, contradicting_evidence, unanswered_questions
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            item.hypothesis_id,
                            investigation_id,
                            item.title,
                            item.description,
                            item.affected_service,
                            item.confidence,
                            item.status,
                            item.supporting_evidence,
                            item.contradicting_evidence,
                            item.unanswered_questions,
                        ),
                    )
            conn.commit()

    def list_hypotheses(self, investigation_id: str):
        from investigator.models.hypothesis import Hypothesis

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT hypothesis_id, investigation_id, title, description,
                           affected_service, confidence, status,
                           supporting_evidence, contradicting_evidence, unanswered_questions
                    FROM hypotheses
                    WHERE investigation_id = %s
                    ORDER BY confidence DESC, hypothesis_id ASC
                    """,
                    (investigation_id,),
                )
                rows = cur.fetchall()
        return [
            Hypothesis(
                hypothesis_id=row[0],
                investigation_id=row[1],
                title=row[2],
                description=row[3],
                affected_service=row[4],
                confidence=float(row[5] or 0),
                status=row[6],
                supporting_evidence=list(row[7] or []),
                contradicting_evidence=list(row[8] or []),
                unanswered_questions=list(row[9] or []),
            )
            for row in rows
        ]

    def update_evidence_links(self, investigation_id: str, evidence: list[Evidence]) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                for item in evidence:
                    cur.execute(
                        """
                        UPDATE evidence
                        SET supports = %s, contradicts = %s
                        WHERE evidence_id = %s AND investigation_id = %s
                        """,
                        (item.supports, item.contradicts, item.evidence_id, investigation_id),
                    )
            conn.commit()

    def save_report(self, report) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reports (report_id, investigation_id, body, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (report_id) DO UPDATE SET body = EXCLUDED.body
                    """,
                    (report.report_id, report.investigation_id, report.model_dump_json(), report.created_at),
                )
            conn.commit()

    def get_report_for_incident(self, incident_id: str):
        from investigator.models.report import Report

        investigation = self.get_investigation_for_incident(incident_id)
        if investigation is None:
            return None
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT body FROM reports
                    WHERE investigation_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (investigation.investigation_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return Report.model_validate_json(row[0])

    def _record_transition(
        self,
        cur,
        investigation_id: str,
        from_status: IncidentStatus | None,
        to_status: IncidentStatus,
        at: datetime,
    ) -> Transition:
        event_id = _new_id("evt")
        cur.execute(
            """
            INSERT INTO investigation_events (event_id, investigation_id, from_status, to_status, at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                event_id,
                investigation_id,
                from_status.value if from_status else None,
                to_status.value,
                at,
            ),
        )
        return Transition(
            event_id=event_id,
            investigation_id=investigation_id,
            from_status=from_status,
            to_status=to_status,
            at=at,
        )

    @staticmethod
    def _incident_from_row(row) -> Incident:
        scope = scope_from_json(row[8]) if len(row) > 8 else None
        notes = row[9] if len(row) > 9 else None
        return Incident(
            incident_id=row[0],
            alert_id=row[1],
            service=row[2],
            severity=row[3],
            started_at=row[4],
            status=IncidentStatus(row[5]),
            created_at=row[6],
            investigation_id=row[7],
            scope=scope,
            notes=notes,
        )

    @staticmethod
    def _investigation_from_row(row) -> Investigation:
        return Investigation(
            investigation_id=row[0],
            incident_id=row[1],
            status=IncidentStatus(row[2]),
            created_at=row[3],
            scope=scope_from_json(row[4]),
            notes=row[5],
        )

    @staticmethod
    def _evidence_from_row(row) -> Evidence:
        return Evidence(
            evidence_id=row[0],
            investigation_id=row[1],
            source=row[2],
            service=row[3],
            timestamp_start=row[4],
            timestamp_end=row[5],
            observation=row[6],
            raw_reference=row[7],
            supports=list(row[8] or []),
            contradicts=list(row[9] or []),
        )

    @staticmethod
    def _timeline_from_row(row) -> TimelineEvent:
        return TimelineEvent(
            event_id=row[0],
            investigation_id=row[1],
            occurred_at=row[2],
            summary=row[3],
            evidence_id=row[4],
        )
