from __future__ import annotations

from dataclasses import dataclass

from investigator.models.evidence import Evidence
from investigator.models.hypothesis import Hypothesis, HypothesisStatus


@dataclass
class VerificationResult:
    hypotheses: list[Hypothesis]
    evidence: list[Evidence]
    top: Hypothesis | None
    sufficient: bool


def _supports(hypothesis: Hypothesis, evidence: Evidence) -> bool:
    service = hypothesis.affected_service.lower()
    obs = evidence.observation.lower()
    title = hypothesis.title.lower()

    if evidence.service.lower() != service and service not in obs:
        if "cascade" not in title and "traffic" not in title:
            return False

    if "deployment" in title and evidence.source == "deployment" and evidence.service.lower() == service:
        return True
    if "deployment" in title and evidence.source == "metric" and evidence.service.lower() == service:
        if "latency" in obs or "error_rate" in obs:
            return _metric_elevated(obs)
    if "database" in title and evidence.source == "deployment" and evidence.service.lower() == service:
        return True
    if "database" in title and evidence.source == "metric" and "database" in obs and evidence.service.lower() == service:
        return True
    if "database" in title and evidence.source == "log" and evidence.service.lower() == service:
        return "timeout" in obs or "timed out" in obs or "slow" in obs
    if "latency" in title or "degradation" in title:
        if evidence.source == "metric" and evidence.service.lower() == service:
            if "latency" in obs or "error_rate" in obs:
                return _metric_elevated(obs)
        if evidence.source == "trace" and evidence.service.lower() == service:
            return True
    if "traffic" in title and evidence.source == "metric" and evidence.service.lower() == service:
        return "request_rate" in obs or "latency" in obs
    if "cascade" in title:
        if evidence.source in {"trace", "metric"} and evidence.service.lower() != service:
            return evidence.service.lower() in {dep.lower() for dep in _downstream_of(service, evidence)}
    return False


def _downstream_of(service: str, evidence: Evidence) -> set[str]:
    return {evidence.service}


def _contradicts(hypothesis: Hypothesis, evidence: Evidence) -> bool:
    service = hypothesis.affected_service.lower()
    if evidence.service.lower() != service:
        return False
    obs = evidence.observation.lower()
    title = hypothesis.title.lower()

    if "deployment" in title and evidence.source == "deployment":
        return "no data" in obs
    if ("latency" in title or "database" in title or "degradation" in title) and evidence.source == "metric":
        if "latency" in obs or "error_rate" in obs:
            return _metric_flat(obs)
    if "traffic" in title and evidence.source == "metric" and "request_rate" in obs:
        return _metric_flat(obs)
    return False


def _metric_elevated(observation: str) -> bool:
    for token in observation.split():
        try:
            value = float(token.rstrip(","))
        except ValueError:
            continue
        if value > 1.0:
            return True
    return "increased" in observation or "above" in observation


def _metric_flat(observation: str) -> bool:
    for token in observation.split():
        try:
            value = float(token.rstrip(","))
        except ValueError:
            continue
        if value <= 1.0:
            return True
    return "no data" in observation or "flat" in observation


def _score(supporting: list[str], contradicting: list[str], evidence: list[Evidence]) -> tuple[float, HypothesisStatus]:
    if contradicting and not supporting:
        return 0.05, "contradicted"
    if not supporting:
        return 0.0, "candidate"

    sources = {item.source for item in evidence if item.evidence_id in supporting}
    coverage = min(1.0, len(supporting) / 3.0)
    quality = min(1.0, len(sources) / 3.0)
    consistency = 1.0 if not contradicting else max(0.2, 1.0 - 0.25 * len(contradicting))
    confidence = round(coverage * quality * consistency, 2)

    if confidence >= 0.55 and not contradicting:
        status: HypothesisStatus = "supported"
    elif contradicting and supporting:
        status = "inconclusive"
    elif contradicting:
        status = "contradicted"
    else:
        status = "candidate"
    return confidence, status


def verify(hypotheses: list[Hypothesis], evidence: list[Evidence], *, threshold: float = 0.55) -> VerificationResult:
    updated_evidence: list[Evidence] = []
    updated_hypotheses: list[Hypothesis] = []

    support_map: dict[str, list[str]] = {item.evidence_id: [] for item in evidence}
    contradict_map: dict[str, list[str]] = {item.evidence_id: [] for item in evidence}

    for hypothesis in hypotheses:
        supporting: list[str] = []
        contradicting: list[str] = []
        for item in evidence:
            if _supports(hypothesis, item):
                supporting.append(item.evidence_id)
                support_map[item.evidence_id].append(hypothesis.hypothesis_id)
            elif _contradicts(hypothesis, item):
                contradicting.append(item.evidence_id)
                contradict_map[item.evidence_id].append(hypothesis.hypothesis_id)

        confidence, status = _score(supporting, contradicting, evidence)
        unanswered: list[str] = []
        if status == "candidate":
            unanswered.append(f"Need stronger telemetry linking {hypothesis.affected_service} to the incident.")

        updated_hypotheses.append(
            hypothesis.model_copy(
                update={
                    "confidence": confidence,
                    "supporting_evidence": supporting,
                    "contradicting_evidence": contradicting,
                    "status": status,
                    "unanswered_questions": unanswered,
                }
            )
        )

    for item in evidence:
        updated_evidence.append(
            item.model_copy(
                update={
                    "supports": support_map[item.evidence_id],
                    "contradicts": contradict_map[item.evidence_id],
                }
            )
        )

    ranked = sorted(updated_hypotheses, key=lambda row: row.confidence, reverse=True)
    top = ranked[0] if ranked else None
    sufficient = top is not None and top.status == "supported" and top.confidence >= threshold
    return VerificationResult(
        hypotheses=ranked,
        evidence=updated_evidence,
        top=top,
        sufficient=sufficient,
    )
