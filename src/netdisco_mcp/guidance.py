"""Bundled agent operating guidance and first-call middleware."""

from __future__ import annotations

import time
from importlib.resources import files

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext


def load_guidance() -> str:
    return files("netdisco_mcp").joinpath("data/GUIDANCE.md").read_text(encoding="utf-8")


class GuidanceGateMiddleware(Middleware):
    """Ensure the operating guide lands in agent context once per activity window."""

    def __init__(self, guidance: str, ttl_seconds: int = 1800) -> None:
        self.guidance = guidance
        self.ttl_seconds = ttl_seconds
        self._guided_until = 0.0

    def _mark_guided(self) -> None:
        self._guided_until = time.monotonic() + self.ttl_seconds

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.name
        if tool_name == "get_guidance":
            self._mark_guided()
            return await call_next(context)

        now = time.monotonic()
        if now >= self._guided_until:
            self._mark_guided()
            raise ToolError(
                "Netdisco operating guidance must be read before API tools are used. "
                "The guide follows below. Read it, then retry the original tool call.\n\n"
                + self.guidance
            )

        self._mark_guided()
        return await call_next(context)

