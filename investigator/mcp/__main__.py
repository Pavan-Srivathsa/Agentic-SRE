from __future__ import annotations

import sys


def main() -> None:
    if sys.version_info < (3, 10):
        raise SystemExit(
            "MCP server requires Python 3.10+. Use `pip install -e \".[mcp]\"` on Python 3.10+."
        )

    from investigator.mcp.server import run_stdio_server

    run_stdio_server()


if __name__ == "__main__":
    main()
