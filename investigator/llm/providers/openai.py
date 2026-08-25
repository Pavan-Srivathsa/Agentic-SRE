from __future__ import annotations

import json
import os
import uuid
from typing import Any

from investigator.models.evidence import Evidence
from investigator.models.hypothesis import Hypothesis
from investigator.models.incident import Incident, Scope

MAX_HYPOTHESES = 5


def _new_id() -> str:
    return f"hyp-{uuid.uuid4().hex[:8]}"


class OpenAIHypothesisGenerator:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def generate(
        self,
        incident: Incident,
        scope: Scope,
        evidence: list[Evidence],
    ) -> list[Hypothesis]:
        from openai import OpenAI

        client = OpenAI()
        payload = {
            "alert_service": incident.service,
            "severity": incident.severity,
            "scoped_services": scope.services,
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "source": item.source,
                    "service": item.service,
                    "observation": item.observation,
                }
                for item in evidence[:20]
            ],
        }
        response = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate at most 5 competing root-cause hypotheses for an SRE incident. "
                        "Return JSON: {\"hypotheses\": [{\"title\",\"description\",\"affected_service\"}]}. "
                        "Do not assign confidence scores."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        parsed: dict[str, Any] = json.loads(raw)
        rows = parsed.get("hypotheses") or []
        hypotheses: list[Hypothesis] = []
        for row in rows[:MAX_HYPOTHESES]:
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=_new_id(),
                    title=row["title"],
                    description=row.get("description") or row["title"],
                    affected_service=row["affected_service"],
                )
            )
        return hypotheses
