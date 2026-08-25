from __future__ import annotations

import uuid
from datetime import datetime, timezone

from investigator.models.evidence import Evidence, TimelineEvent
from investigator.models.incident import AlertIngest, Incident, IncidentStatus, Investigation, Transition


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class MemoryStore:
    def __init__(self) -> None:
        self.alerts: dict[str, dict] = {}
        self.incidents: dict[str, Incident] = {}
        self.investigations: dict[str, Investigation] = {}
        self.incident_by_investigation: dict[str, str] = {}
        self.transitions: list[Transition] = []
        self.evidence: list[Evidence] = []
        self.timeline: list[TimelineEvent] = []
        self.hypotheses: dict[str, list] = {}
        self.reports: dict[str, object] = {}
        self.dependencies: set[tuple[str, str]] = set()

    def run_migrations(self, migrations_dir=None) -> None:
        return None

    def seed_dependencies(self) -> int:
        from investigator.connectors.dependencies import load_graph

        graph = load_graph()
        count = 0
        for service, deps in graph.items():
            for dep in deps:
                key = (service, dep)
                if key not in self.dependencies:
                    self.dependencies.add(key)
                    count += 1
        return count

    def ingest_alert(self, payload: AlertIngest) -> Incident:
        incident_id = _new_id("inc")
        investigation_id = _new_id("inv")
        now = _utcnow()
        self.alerts[payload.alert_id] = payload.model_dump()
        incident = Incident(
            incident_id=incident_id,
            alert_id=payload.alert_id,
            service=payload.service,
            severity=payload.severity,
            started_at=payload.starts_at,
            status=IncidentStatus.RECEIVED,
            created_at=now,
            investigation_id=investigation_id,
        )
        investigation = Investigation(
            investigation_id=investigation_id,
            incident_id=incident_id,
            status=IncidentStatus.RECEIVED,
            created_at=now,
        )
        self.incidents[incident_id] = incident
        self.investigations[investigation_id] = investigation
        self.incident_by_investigation[investigation_id] = incident_id
        self._record_transition(investigation_id, None, IncidentStatus.RECEIVED, now)
        return incident

    def get_incident(self, incident_id: str) -> Incident | None:
        incident = self.incidents.get(incident_id)
        if not incident:
            return None
        inv = self.get_investigation_for_incident(incident_id)
        if inv:
            return Incident(
                incident_id=incident.incident_id,
                alert_id=incident.alert_id,
                service=incident.service,
                severity=incident.severity,
                started_at=incident.started_at,
                status=inv.status,
                created_at=incident.created_at,
                investigation_id=inv.investigation_id,
                scope=inv.scope,
                notes=inv.notes,
            )
        return incident

    def get_investigation(self, investigation_id: str) -> Investigation | None:
        return self.investigations.get(investigation_id)

    def get_investigation_for_incident(self, incident_id: str) -> Investigation | None:
        for inv in self.investigations.values():
            if inv.incident_id == incident_id:
                return inv
        return None

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
        inv = self.investigations[investigation_id]
        if append_notes:
            notes = f"{inv.notes or ''}\n{append_notes}".strip()
        inv.status = nxt
        if scope is not None:
            inv.scope = scope
        if notes is not None:
            inv.notes = notes
        incident = self.incidents[inv.incident_id]
        self.incidents[inv.incident_id] = Incident(
            incident_id=incident.incident_id,
            alert_id=incident.alert_id,
            service=incident.service,
            severity=incident.severity,
            started_at=incident.started_at,
            status=nxt,
            created_at=incident.created_at,
            investigation_id=investigation_id,
            scope=inv.scope,
            notes=inv.notes,
        )
        return self._record_transition(investigation_id, current, nxt, _utcnow())

    def add_evidence(self, evidence: Evidence) -> None:
        self.evidence.append(evidence)

    def list_evidence(self, investigation_id: str) -> list[Evidence]:
        return sorted(
            [item for item in self.evidence if item.investigation_id == investigation_id],
            key=lambda item: item.timestamp_start,
        )

    def add_timeline_event(self, event: TimelineEvent) -> None:
        self.timeline.append(event)

    def list_timeline(self, investigation_id: str) -> list[TimelineEvent]:
        return sorted(
            [item for item in self.timeline if item.investigation_id == investigation_id],
            key=lambda item: (item.occurred_at, item.event_id),
        )

    def get_alert(self, alert_id: str):
        from investigator.models.incident import Alert

        raw = self.alerts.get(alert_id)
        if not raw:
            return None
        return Alert.model_validate(raw)

    def replace_hypotheses(self, investigation_id: str, hypotheses) -> None:
        self.hypotheses[investigation_id] = [
            item.model_copy(update={"investigation_id": investigation_id}) for item in hypotheses
        ]

    def list_hypotheses(self, investigation_id: str):
        return list(self.hypotheses.get(investigation_id, []))

    def update_evidence_links(self, investigation_id: str, evidence: list[Evidence]) -> None:
        by_id = {item.evidence_id: item for item in evidence}
        self.evidence = [
            by_id.get(item.evidence_id, item)
            if item.investigation_id == investigation_id
            else item
            for item in self.evidence
        ]

    def save_report(self, report) -> None:
        self.reports[report.incident_id] = report

    def get_report_for_incident(self, incident_id: str):
        return self.reports.get(incident_id)

    def _record_transition(
        self,
        investigation_id: str,
        from_status: IncidentStatus | None,
        to_status: IncidentStatus,
        at: datetime,
    ) -> Transition:
        event = Transition(
            event_id=_new_id("evt"),
            investigation_id=investigation_id,
            from_status=from_status,
            to_status=to_status,
            at=at,
        )
        self.transitions.append(event)
        return event
