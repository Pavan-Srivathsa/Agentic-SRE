from __future__ import annotations

from dataclasses import dataclass, field

from investigator.connectors.deployments import DeploymentsClient
from investigator.connectors.http import ConnectorUnavailable
from investigator.connectors.logs import LogsClient
from investigator.connectors.metrics import MetricsClient
from investigator.connectors.traces import TracesClient
from investigator.models.incident import Incident, IncidentStatus, Scope
from investigator.orchestration.evidence_mapping import (
    evidence_from_deployment,
    evidence_from_log,
    evidence_from_metric,
    evidence_from_trace,
    timeline_from_evidence,
)
from investigator.orchestration.scoping import combined_window
from investigator.orchestration.state_machine import transition

MAX_TOOL_CALLS = 12


@dataclass
class CollectorBundle:
    metrics: MetricsClient | None = None
    logs: LogsClient | None = None
    traces: TracesClient | None = None
    deployments: DeploymentsClient | None = None


@dataclass
class CollectionResult:
    notes: list[str] = field(default_factory=list)
    call_count: int = 0


class BaselineCollector:
    def __init__(self, bundle: CollectorBundle | None = None) -> None:
        self.metrics = (bundle.metrics if bundle else None) or MetricsClient()
        self.logs = (bundle.logs if bundle else None) or LogsClient()
        self.traces = (bundle.traces if bundle else None) or TracesClient()
        self.deployments = (bundle.deployments if bundle else None) or DeploymentsClient()

    async def collect(self, store, incident: Incident, scope: Scope) -> CollectionResult:
        investigation_id = incident.investigation_id
        if not investigation_id:
            raise ValueError("incident missing investigation_id")

        result = CollectionResult()
        deploy_window = combined_window(scope.incident, scope.baseline)

        for service in scope.services:
            if result.call_count >= MAX_TOOL_CALLS:
                result.notes.append(f"tool budget exhausted before collecting all services (cap {MAX_TOOL_CALLS})")
                break

            for metric in ("request_latency", "error_rate"):
                if result.call_count >= MAX_TOOL_CALLS:
                    break
                try:
                    series = await self.metrics.query_metrics(
                        service,
                        metric,
                        scope.incident.start,
                        scope.incident.end,
                    )
                    evidence = evidence_from_metric(
                        series,
                        investigation_id=investigation_id,
                        window_start=scope.incident.start,
                        window_end=scope.incident.end,
                    )
                    store.add_evidence(evidence)
                    store.add_timeline_event(timeline_from_evidence(evidence))
                    result.call_count += 1
                except ConnectorUnavailable as exc:
                    result.notes.append(f"{exc.connector} unavailable for {service}/{metric}: {exc}")
                except Exception as exc:
                    result.notes.append(f"metrics failed for {service}/{metric}: {exc}")

            if result.call_count >= MAX_TOOL_CALLS:
                continue

            try:
                logs = await self.logs.search(
                    service,
                    scope.incident.start,
                    scope.incident.end,
                    level="ERROR",
                )
                for event in logs[:3]:
                    evidence = evidence_from_log(
                        event,
                        investigation_id=investigation_id,
                        window_end=scope.incident.end,
                    )
                    store.add_evidence(evidence)
                    store.add_timeline_event(timeline_from_evidence(evidence))
                result.call_count += 1
            except ConnectorUnavailable as exc:
                result.notes.append(f"{exc.connector} unavailable for {service} logs: {exc}")
            except Exception as exc:
                result.notes.append(f"log search failed for {service}: {exc}")

            if result.call_count >= MAX_TOOL_CALLS:
                continue

            try:
                deployments = self.deployments.get_recent_deployments(
                    service,
                    deploy_window.start,
                    deploy_window.end,
                )
                for deployment in deployments[:2]:
                    evidence = evidence_from_deployment(
                        deployment,
                        investigation_id=investigation_id,
                        window_start=deploy_window.start,
                        window_end=deploy_window.end,
                    )
                    store.add_evidence(evidence)
                    store.add_timeline_event(timeline_from_evidence(evidence))
                result.call_count += 1
            except Exception as exc:
                result.notes.append(f"deployments failed for {service}: {exc}")

        if scope.primary_service in scope.services and result.call_count < MAX_TOOL_CALLS:
            try:
                traces = await self.traces.find_slow_traces(
                    scope.primary_service,
                    scope.incident.start,
                    scope.incident.end,
                )
                for trace in traces[:3]:
                    evidence = evidence_from_trace(
                        trace,
                        investigation_id=investigation_id,
                        window_start=scope.incident.start,
                        window_end=scope.incident.end,
                    )
                    store.add_evidence(evidence)
                    store.add_timeline_event(timeline_from_evidence(evidence))
                result.call_count += 1
            except ConnectorUnavailable as exc:
                result.notes.append(f"{exc.connector} unavailable for slow traces: {exc}")
            except Exception as exc:
                result.notes.append(f"trace search failed: {exc}")

        return result


async def run_investigation(store, incident_id: str, collector: BaselineCollector | None = None) -> Incident:
    incident = store.get_incident(incident_id)
    if incident is None:
        raise KeyError(f"incident not found: {incident_id}")
    investigation = store.get_investigation_for_incident(incident_id)
    if investigation is None:
        raise KeyError(f"investigation not found for incident: {incident_id}")

    inv_id = investigation.investigation_id
    current = investigation.status

    transition(current, IncidentStatus.SCOPING)
    store.advance_status(inv_id, current, IncidentStatus.SCOPING)
    current = IncidentStatus.SCOPING

    from investigator.models.incident import AlertIngest

    alert = AlertIngest(
        alert_id=incident.alert_id,
        alert_name=incident.alert_id,
        service=incident.service,
        severity=incident.severity,
        starts_at=incident.started_at,
    )
    from investigator.orchestration.scoping import build_scope

    scope = build_scope(alert)

    transition(current, IncidentStatus.BASELINE_COLLECTION)
    store.advance_status(inv_id, current, IncidentStatus.BASELINE_COLLECTION, scope=scope)
    current = IncidentStatus.BASELINE_COLLECTION

    collector = collector or BaselineCollector()
    incident_with_scope = store.get_incident(incident_id)
    if incident_with_scope is None:
        raise KeyError(f"incident not found after scoping: {incident_id}")

    collection = await collector.collect(store, incident_with_scope, scope)
    if collection.notes:
        store.advance_status(
            inv_id,
            current,
            IncidentStatus.BASELINE_COLLECTION,
            append_notes="\n".join(collection.notes),
        )

    incident_after_baseline = store.get_incident(incident_id)
    if incident_after_baseline is None:
        raise KeyError(f"incident not found after collection: {incident_id}")

    from investigator.orchestration.diagnosis import run_diagnosis

    final = await run_diagnosis(store, incident_after_baseline, baseline_calls=collection.call_count)
    return final
