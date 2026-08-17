"""Build the complete Netdisco MCP server."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware

from .auth import BearerTokenVerifier
from .config import Settings
from .guidance import GuidanceGateMiddleware, load_guidance
from .spec import Operation, fetch_swagger, iter_operations, normalize_spec, search_operations

LOG = logging.getLogger("netdisco_mcp")

SERVER_INSTRUCTIONS = """\
Call get_guidance before using any Netdisco API tool. This server exposes the
complete Netdisco REST API, including mutations when read-only mode is off.
Use find_capability when you are unsure which tool maps to a task. Prefer
search and object GET tools before reports. Never infer that a mutation failed
solely from a timeout; verify current state before retrying.
"""


def _api_client(settings: Settings) -> httpx.AsyncClient:
    headers = {"Accept": "application/json"}
    authorization = settings.authorization_header()
    if authorization:
        headers["Authorization"] = authorization
    auth = None
    if settings.username and settings.password:
        auth = httpx.BasicAuth(settings.username, settings.password)
    return httpx.AsyncClient(
        base_url=settings.netdisco_url,
        headers=headers,
        auth=auth,
        verify=settings.tls_verify,
        timeout=settings.request_timeout,
        follow_redirects=True,
    )


def build_server(settings: Settings) -> tuple[FastMCP, list[Operation]]:
    source = fetch_swagger(
        settings.spec_url,
        verify=settings.tls_verify,
        timeout=settings.request_timeout,
    )
    spec = normalize_spec(
        source,
        base_url=settings.netdisco_url,
        read_only=settings.read_only,
    )
    operations = list(iter_operations(spec))
    guidance = load_guidance()

    auth = (
        BearerTokenVerifier(settings.mcp_bearer_token)
        if settings.mcp_bearer_token
        else None
    )
    main = FastMCP(
        name="Netdisco MCP",
        instructions=SERVER_INSTRUCTIONS,
        auth=auth,
    )

    @main.tool(
        name="get_guidance",
        description=(
            "Read the Netdisco operating guide. Agents must call this before any other "
            "tool at the start of a working session."
        ),
        tags={"guidance", "read-only"},
    )
    def get_guidance(topic: str | None = None) -> str:
        """Return the complete guide, optionally highlighting a relevant section."""
        if not topic:
            return guidance
        topic_key = topic.casefold()
        sections = guidance.split("\n## ")
        matches = [section for section in sections if topic_key in section.casefold()]
        if not matches:
            return guidance
        return "\n## ".join(matches)

    @main.tool(
        name="find_capability",
        description=(
            "Search the complete generated Netdisco tool catalog by task, route, tag, "
            "or HTTP method. Use this instead of guessing tool names."
        ),
        tags={"guidance", "discovery", "read-only"},
    )
    def find_capability(
        query: str = "",
        tag: str | None = None,
        method: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        matches = search_operations(
            operations,
            query=query,
            tag=tag,
            method=method,
            limit=limit,
        )
        return {
            "matches": matches,
            "returned": len(matches),
            "total_tools": len(operations),
            "read_only_mode": settings.read_only,
            "hint": "Call get_guidance once, then invoke the named tool directly.",
        }

    api = FastMCP.from_openapi(
        openapi_spec=spec,
        client=_api_client(settings),
        name="Netdisco REST API",
    )
    main.mount(api)

    if settings.guidance_gate:
        main.add_middleware(GuidanceGateMiddleware(guidance, settings.guidance_ttl))
    main.add_middleware(
        ResponseLimitingMiddleware(
            max_size=settings.max_response_chars,
            truncation_suffix=(
                "\n\n[Response truncated by Netdisco MCP. Narrow the query, request a "
                "specific device/port, or use a more targeted endpoint.]"
            ),
        )
    )

    LOG.info(
        "Loaded %s Netdisco API operations (%s mutations, read_only=%s)",
        len(operations),
        sum(operation.mutation for operation in operations),
        settings.read_only,
    )
    return main, operations
