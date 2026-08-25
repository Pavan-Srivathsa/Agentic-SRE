from investigator.connectors.dependencies import list_dependencies

GRAPH = {
    "api-gateway": ["order-service"],
    "order-service": ["payment-service", "inventory-service", "postgres"],
    "payment-service": ["postgres"],
    "inventory-service": ["postgres"],
}


def test_depth_two_from_gateway() -> None:
    levels = list_dependencies("api-gateway", depth=2, graph=GRAPH)
    assert levels["depth_0"] == ["api-gateway"]
    assert levels["depth_1"] == ["order-service"]
    assert set(levels["depth_2"]) == {"payment-service", "inventory-service", "postgres"}


def test_does_not_query_unrelated_services() -> None:
    levels = list_dependencies("payment-service", depth=1, graph=GRAPH)
    flat = {svc for group in levels.values() for svc in group}
    assert "api-gateway" not in flat
    assert "postgres" in flat
