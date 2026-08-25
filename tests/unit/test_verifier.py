from datetime import datetime, timezone

from investigator.models.evidence import Evidence
from investigator.models.hypothesis import Hypothesis
from investigator.orchestration.verifier import verify


def _evidence(evidence_id: str, source: str, service: str, observation: str) -> Evidence:
    ts = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    return Evidence(
        evidence_id=evidence_id,
        investigation_id="inv-1",
        source=source,
        service=service,
        timestamp_start=ts,
        timestamp_end=ts,
        observation=observation,
        raw_reference=evidence_id,
    )


def test_payment_deployment_supported_inventory_contradicted() -> None:
    hypotheses = [
        Hypothesis(
            hypothesis_id="hyp-pay",
            title="payment-service deployment regression",
            description="Recent payment deploy caused regression.",
            affected_service="payment-service",
        ),
        Hypothesis(
            hypothesis_id="hyp-inv",
            title="inventory-service latency degradation",
            description="Inventory slowed down.",
            affected_service="inventory-service",
        ),
    ]
    evidence = [
        _evidence("ev-dep", "deployment", "payment-service", "deployment v17 (abc123d) on payment-service"),
        _evidence(
            "ev-pay-lat",
            "metric",
            "payment-service",
            "p95 request_latency last point 2.5000",
        ),
        _evidence(
            "ev-pay-db",
            "metric",
            "payment-service",
            "p95 database_latency last point 1.8000",
        ),
        _evidence(
            "ev-inv-lat",
            "metric",
            "inventory-service",
            "p95 request_latency last point 0.2000",
        ),
    ]
    result = verify(hypotheses, evidence)
    by_id = {item.hypothesis_id: item for item in result.hypotheses}
    assert by_id["hyp-pay"].status == "supported"
    assert by_id["hyp-pay"].confidence >= 0.55
    assert by_id["hyp-inv"].status in {"contradicted", "candidate"}
    assert result.sufficient is True
    assert result.top is not None
    assert result.top.affected_service == "payment-service"
