from __future__ import annotations

from investigator.models.incident import Incident, IncidentStatus
from investigator.orchestration.hypotheses import get_hypothesis_generator
from investigator.orchestration.planner import InvestigationBudget, TargetedCollector, plan_next_actions
from investigator.orchestration.reporter import generate_report
from investigator.orchestration.state_machine import transition
from investigator.orchestration.verifier import verify


async def run_diagnosis(store, incident: Incident, *, baseline_calls: int = 0) -> Incident:
    investigation = store.get_investigation_for_incident(incident.incident_id)
    if investigation is None or investigation.scope is None:
        raise KeyError(f"investigation scope missing for incident: {incident.incident_id}")

    inv_id = investigation.investigation_id
    current = investigation.status
    scope = investigation.scope
    alert = store.get_alert(incident.alert_id)
    alert_name = alert.alert_name if alert else incident.alert_id

    transition(current, IncidentStatus.HYPOTHESIS_GENERATION)
    store.advance_status(inv_id, current, IncidentStatus.HYPOTHESIS_GENERATION)
    current = IncidentStatus.HYPOTHESIS_GENERATION

    evidence = store.list_evidence(inv_id)
    generator = get_hypothesis_generator()
    hypotheses = generator.generate(incident, scope, evidence)
    store.replace_hypotheses(inv_id, hypotheses)

    transition(current, IncidentStatus.EVIDENCE_COLLECTION)
    store.advance_status(inv_id, current, IncidentStatus.EVIDENCE_COLLECTION)
    current = IncidentStatus.EVIDENCE_COLLECTION

    budget = InvestigationBudget(used_tool_calls=baseline_calls)
    collector = TargetedCollector()
    verification = verify(hypotheses, evidence)
    store.update_evidence_links(inv_id, verification.evidence)
    store.replace_hypotheses(inv_id, verification.hypotheses)

    rounds = 0
    while not verification.sufficient and rounds < 2:
        plan = plan_next_actions(scope, verification.hypotheses, store.list_evidence(inv_id), budget)
        if not plan.actions:
            break
        await collector.execute(store, inv_id, scope, plan.actions, budget)
        evidence = store.list_evidence(inv_id)
        verification = verify(store.list_hypotheses(inv_id), evidence)
        store.update_evidence_links(inv_id, verification.evidence)
        store.replace_hypotheses(inv_id, verification.hypotheses)
        rounds += 1

    transition(current, IncidentStatus.VERIFICATION)
    store.advance_status(inv_id, current, IncidentStatus.VERIFICATION)
    current = IncidentStatus.VERIFICATION

    if verification.top and verification.sufficient:
        transition(current, IncidentStatus.DIAGNOSED)
        store.advance_status(inv_id, current, IncidentStatus.DIAGNOSED)
        current = IncidentStatus.DIAGNOSED

        timeline = store.list_timeline(inv_id)
        report = generate_report(
            incident,
            alert_name,
            verification.top,
            store.list_evidence(inv_id),
            timeline,
        )
        store.save_report(report)

        transition(current, IncidentStatus.REPORT_GENERATED)
        store.advance_status(inv_id, current, IncidentStatus.REPORT_GENERATED)
    else:
        transition(current, IncidentStatus.INSUFFICIENT_EVIDENCE)
        store.advance_status(
            inv_id,
            current,
            IncidentStatus.INSUFFICIENT_EVIDENCE,
            append_notes="Unable to reach supported hypothesis threshold.",
        )

    final = store.get_incident(incident.incident_id)
    if final is None:
        raise KeyError(f"incident not found after diagnosis: {incident.incident_id}")
    return final
