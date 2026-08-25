from __future__ import annotations

import uuid
from datetime import datetime, timezone

from investigator.models.evidence import Evidence, TimelineEvent
from investigator.models.hypothesis import Hypothesis
from investigator.models.incident import Incident
from investigator.models.report import Report


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_report(
    incident: Incident,
    alert_name: str,
    hypothesis: Hypothesis,
    evidence: list[Evidence],
    timeline: list[TimelineEvent],
) -> Report:
    linked = [item for item in evidence if item.evidence_id in hypothesis.supporting_evidence]
    if not linked:
        linked = evidence[:5]

    evidence_ids = [item.evidence_id for item in linked]
    lines = [
        f"Incident: {alert_name}",
        "",
        "Root cause:",
        hypothesis.description,
        "",
        f"Confidence: {hypothesis.confidence:.2f}",
        "",
        "Evidence:",
    ]
    for index, item in enumerate(linked, start=1):
        lines.append(f"{index}. [{item.evidence_id}] {item.observation}")

    lines.extend(["", "Timeline:"])
    for event in timeline[:10]:
        lines.append(f"- {event.occurred_at.isoformat()} {event.summary}")

    action = _recommended_action(hypothesis)
    lines.extend(["", "Recommended action:", action])

    body = "\n".join(lines)
    return Report(
        report_id=_new_id("rep"),
        investigation_id=incident.investigation_id or "",
        incident_id=incident.incident_id,
        alert_name=alert_name,
        root_cause=hypothesis.description,
        root_service=hypothesis.affected_service,
        confidence=hypothesis.confidence,
        hypothesis_id=hypothesis.hypothesis_id,
        evidence_ids=evidence_ids,
        recommended_action=action,
        body=body,
        created_at=_utcnow(),
    )


def _recommended_action(hypothesis: Hypothesis) -> str:
    title = hypothesis.title.lower()
    service = hypothesis.affected_service
    if "deployment" in title:
        return f"Review recent {service} deployment and consider rollback while validating database query changes."
    if "database" in title:
        return f"Inspect {service} database query plans and recent schema or ORM changes."
    if "traffic" in title:
        return f"Validate traffic patterns to {service} and scale or rate-limit if saturation is confirmed."
    return f"Continue focused investigation on {service} with additional metrics and traces."
