from investigator.connectors.traces import format_trace_tree, parse_trace_payload


def test_parse_and_format_trace_tree() -> None:
    payload = {
        "batches": [
            {
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "api-gateway"}}]},
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "spanId": "aa",
                                "parentSpanId": "",
                                "name": "POST /checkout",
                                "startTimeUnixNano": "0",
                                "endTimeUnixNano": "2450000000",
                            }
                        ]
                    }
                ],
            },
            {
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "payment-service"}}]},
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "spanId": "bb",
                                "parentSpanId": "aa",
                                "name": "POST /charge",
                                "startTimeUnixNano": "100000000",
                                "endTimeUnixNano": "2200000000",
                            }
                        ]
                    }
                ],
            },
        ]
    }
    tree = parse_trace_payload(payload, "abc")
    assert "payment-service" in tree.services
    text = format_trace_tree(tree)
    assert "api-gateway" in text
    assert "payment-service" in text
    assert tree.root is not None
    assert tree.root.children
