"""Claude Desktop stdio proxy for the authenticated remote server."""

from __future__ import annotations

import os

from fastmcp import Client, FastMCP
from fastmcp.client.auth import BearerAuth
from fastmcp.server import create_proxy


def build_proxy() -> FastMCP:
    url = os.getenv(
        "NETDISCO_MCP_URL",
        "https://netdisco-mcp.san-marcos.net/mcp",
    )
    token = os.getenv("NETDISCO_MCP_BEARER_TOKEN", "")
    if not token:
        raise ValueError("NETDISCO_MCP_BEARER_TOKEN is required")

    client = Client(url, auth=BearerAuth(token=token))
    return create_proxy(client, name="Netdisco MCP")


mcp = build_proxy()


if __name__ == "__main__":
    mcp.run(transport="stdio")
