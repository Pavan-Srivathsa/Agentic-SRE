from __future__ import annotations

import os
import uuid

from investigator.models.evidence import Evidence
from investigator.models.hypothesis import Hypothesis
from investigator.models.incident import Incident, Scope

MAX_HYPOTHESES = 5


def _new_id() -> str:
    return f"hyp-{uuid.uuid4().hex[:8]}"


def _rule_based_hypotheses(incident: Incident, scope: Scope) -> list[Hypothesis]:
    candidates: list[Hypothesis] = []
    downstream = [svc for svc in scope.services if svc != scope.primary_service]

    for service in downstream[:3]:
        candidates.append(
            Hypothesis(
                hypothesis_id=_new_id(),
                title=f"{service} deployment regression",
                description=f"A recent deployment to {service} introduced a performance regression.",
                affected_service=service,
            )
        )
        candidates.append(
            Hypothesis(
                hypothesis_id=_new_id(),
                title=f"{service} database latency regression",
                description=f"Database queries on {service} became slower during the incident window.",
                affected_service=service,
            )
        )

    candidates.append(
        Hypothesis(
            hypothesis_id=_new_id(),
            title=f"{scope.primary_service} traffic overload",
            description="Elevated request volume caused saturation at the alerting service.",
            affected_service=scope.primary_service,
        )
    )
    candidates.append(
        Hypothesis(
            hypothesis_id=_new_id(),
            title="Downstream dependency cascade",
            description="Latency propagated from a downstream dependency to the alerting service.",
            affected_service=scope.primary_service,
        )
    )

    seen_titles: set[str] = set()
    unique: list[Hypothesis] = []
    for item in candidates:
        if item.title in seen_titles:
            continue
        seen_titles.add(item.title)
        unique.append(item)
        if len(unique) >= MAX_HYPOTHESES:
            break
    return unique


def get_hypothesis_generator():
    if os.getenv("OPENAI_API_KEY"):
        from investigator.llm.providers.openai import OpenAIHypothesisGenerator

        return OpenAIHypothesisGenerator()
    return RuleBasedHypothesisGenerator()


class RuleBasedHypothesisGenerator:
    def generate(
        self,
        incident: Incident,
        scope: Scope,
        evidence: list[Evidence],
    ) -> list[Hypothesis]:
        return _rule_based_hypotheses(incident, scope)
