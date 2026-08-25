from __future__ import annotations

from dataclasses import dataclass, field

from investigator.connectors.deployments import DeploymentsClient
from investigator.connectors.github import GitClient
from investigator.connectors.http import ConnectorUnavailable
from investigator.connectors.metrics import MetricsClient
from investigator.models.evidence import Evidence
from investigator.models.hypothesis import Hypothesis
from investigator.models.incident import Scope
from investigator.orchestration.evidence_mapping import (
    evidence_from_metric,
    timeline_from_evidence,
)
from investigator.orchestration.scoping import combined_window


@dataclass
class InvestigationBudget:
    max_tool_calls: int = 25
    max_metric_queries: int = 8
    max_change_queries: int = 3
    used_tool_calls: int = 0
    used_metric_queries: int = 0
    used_change_queries: int = 0

    def can_metric(self) -> bool:
        return self.used_tool_calls < self.max_tool_calls and self.used_metric_queries < self.max_metric_queries

    def can_change(self) -> bool:
        return self.used_tool_calls < self.max_tool_calls and self.used_change_queries < self.max_change_queries

    def spend_metric(self) -> None:
        self.used_tool_calls += 1
        self.used_metric_queries += 1

    def spend_change(self) -> None:
        self.used_tool_calls += 1
        self.used_change_queries += 1


@dataclass
class PlannedAction:
    tool: str
    service: str
    detail: str


@dataclass
class PlannerResult:
    actions: list[PlannedAction] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def plan_next_actions(
    scope: Scope,
    hypotheses: list[Hypothesis],
    evidence: list[Evidence],
    budget: InvestigationBudget,
) -> PlannerResult:
    result = PlannerResult()
    ranked = sorted(hypotheses, key=lambda item: item.confidence, reverse=True)
    top = ranked[0] if ranked else None
    if top is None:
        return result

    services_with_db_metric = {
        item.service
        for item in evidence
        if item.source == "metric" and "database" in item.observation.lower()
    }
    services_with_commit = {
        item.service for item in evidence if item.source == "commit"
    }

    for service in scope.services:
        if "database" in top.title.lower() or "deployment" in top.title.lower():
            if service not in services_with_db_metric and budget.can_metric():
                result.actions.append(
                    PlannedAction(
                        tool="query_metrics",
                        service=service,
                        detail="database_latency",
                    )
                )
        if "deployment" in top.title.lower():
            deployment_evidence = [
                item for item in evidence if item.source == "deployment" and item.service == service
            ]
            if deployment_evidence and service not in services_with_commit and budget.can_change():
                result.actions.append(
                    PlannedAction(
                        tool="get_commit_diff",
                        service=service,
                        detail=deployment_evidence[0].raw_reference,
                    )
                )

    if not result.actions and top.status == "candidate" and budget.can_metric():
        for service in scope.services[:2]:
            result.actions.append(
                PlannedAction(
                    tool="query_metrics",
                    service=service,
                    detail="request_latency",
                )
            )
    return result


class TargetedCollector:
    def __init__(
        self,
        metrics: MetricsClient | None = None,
        deployments: DeploymentsClient | None = None,
        git: GitClient | None = None,
    ) -> None:
        self.metrics = metrics or MetricsClient()
        self.deployments = deployments or DeploymentsClient()
        self.git = git or GitClient()

    async def execute(
        self,
        store,
        investigation_id: str,
        scope: Scope,
        actions: list[PlannedAction],
        budget: InvestigationBudget,
    ) -> list[Evidence]:
        collected: list[Evidence] = []
        combined_window(scope.incident, scope.baseline)

        for action in actions:
            if budget.used_tool_calls >= budget.max_tool_calls:
                break
            try:
                if action.tool == "query_metrics" and budget.can_metric():
                    series = await self.metrics.query_metrics(
                        action.service,
                        action.detail,
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
                    collected.append(evidence)
                    budget.spend_metric()
                elif action.tool == "get_commit_diff" and budget.can_change():
                    commit = self._commit_sha_for_service(action.service, scope)
                    if not commit:
                        continue
                    diff = self.git.get_commit_diff(action.service, commit)
                    from investigator.orchestration.evidence_mapping import _new_id

                    evidence = Evidence(
                        evidence_id=_new_id("ev"),
                        investigation_id=investigation_id,
                        source="commit",
                        service=action.service,
                        timestamp_start=diff.committed_at,
                        timestamp_end=scope.incident.end,
                        observation=f"commit {diff.commit_sha[:7]}: {diff.message}",
                        raw_reference=diff.commit_sha,
                    )
                    store.add_evidence(evidence)
                    store.add_timeline_event(timeline_from_evidence(evidence))
                    collected.append(evidence)
                    budget.spend_change()
            except ConnectorUnavailable:
                budget.spend_metric() if action.tool == "query_metrics" else budget.spend_change()
                continue
            except Exception:
                continue
        return collected

    def _commit_sha_for_service(self, service: str, scope: Scope) -> str | None:
        deployments = self.deployments.get_recent_deployments(
            service,
            scope.incident.start,
            scope.incident.end,
        )
        return deployments[0].commit_sha if deployments else None
