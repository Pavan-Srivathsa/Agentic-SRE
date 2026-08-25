from investigator.connectors.metrics import render_promql


def test_latency_template_is_bounded_promql() -> None:
    query = render_promql("payment-service", "request_latency")
    assert "payment-service" in query
    assert "histogram_quantile(0.95" in query
    assert "http_request_duration_seconds_bucket" in query


def test_p50_swaps_quantile() -> None:
    query = render_promql("api-gateway", "request_latency", aggregation="p50")
    assert "histogram_quantile(0.50" in query


def test_unknown_metric_rejected() -> None:
    try:
        render_promql("api-gateway", "not_a_metric")  # type: ignore[arg-type]
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
