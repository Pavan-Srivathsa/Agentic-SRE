from __future__ import annotations

from investigator.models.incident import IncidentStatus


class InvalidTransition(ValueError):
    pass


ALLOWED: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.RECEIVED: {IncidentStatus.SCOPING, IncidentStatus.FAILED},
    IncidentStatus.SCOPING: {IncidentStatus.BASELINE_COLLECTION, IncidentStatus.FAILED},
    IncidentStatus.BASELINE_COLLECTION: {
        IncidentStatus.HYPOTHESIS_GENERATION,
        IncidentStatus.INSUFFICIENT_EVIDENCE,
        IncidentStatus.FAILED,
        IncidentStatus.BASELINE_COLLECTION,
    },
    IncidentStatus.HYPOTHESIS_GENERATION: {IncidentStatus.EVIDENCE_COLLECTION, IncidentStatus.FAILED},
    IncidentStatus.EVIDENCE_COLLECTION: {IncidentStatus.VERIFICATION, IncidentStatus.FAILED},
    IncidentStatus.VERIFICATION: {
        IncidentStatus.DIAGNOSED,
        IncidentStatus.INSUFFICIENT_EVIDENCE,
        IncidentStatus.FAILED,
        IncidentStatus.SCOPING,
    },
    IncidentStatus.DIAGNOSED: {IncidentStatus.REPORT_GENERATED, IncidentStatus.FAILED},
    IncidentStatus.REPORT_GENERATED: set(),
    IncidentStatus.INSUFFICIENT_EVIDENCE: {IncidentStatus.FAILED},
    IncidentStatus.FAILED: set(),
}


def transition(current: IncidentStatus, nxt: IncidentStatus) -> IncidentStatus:
    allowed = ALLOWED.get(current, set())
    if nxt not in allowed:
        raise InvalidTransition(f"{current.value} -> {nxt.value} is not allowed")
    return nxt
