import sys

import pytest


@pytest.mark.skipif(sys.version_info < (3, 10), reason="MCP SDK requires Python 3.10+")
def test_mcp_server_registers_tools() -> None:
    pytest.importorskip("mcp")
    from investigator.mcp import server

    assert hasattr(server, "run_stdio_server")
