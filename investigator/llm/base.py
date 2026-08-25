from __future__ import annotations

from typing import Protocol

from investigator.models.evidence import Evidence
from investigator.models.hypothesis import Hypothesis
from investigator.models.incident import Incident, Scope


class HypothesisGenerator(Protocol):
    def generate(
        self,
        incident: Incident,
        scope: Scope,
        evidence: list[Evidence],
    ) -> list[Hypothesis]: ...
