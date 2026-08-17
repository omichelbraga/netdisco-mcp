"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import logging

from . import __version__
from .config import Settings
from .server import build_server


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the complete Netdisco MCP server")
    parser.add_argument("--check", action="store_true", help="validate the live spec and print coverage")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main() -> None:
    args = _parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    mcp, operations = build_server(settings)

    if args.check:
        print(
            json.dumps(
                {
                    "netdisco_url": settings.netdisco_url,
                    "spec_url": settings.spec_url,
                    "read_only": settings.read_only,
                    "api_operations": len(operations),
                    "read_operations": sum(not item.mutation for item in operations),
                    "mutation_operations": sum(item.mutation for item in operations),
                    "mcp_tools_total": len(operations) + 2,
                    "tags": sorted({item.tag for item in operations}),
                },
                indent=2,
            )
        )
        return

    if settings.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport="streamable-http",
            host=settings.http_host,
            port=settings.http_port,
            path="/mcp",
        )


if __name__ == "__main__":
    main()
