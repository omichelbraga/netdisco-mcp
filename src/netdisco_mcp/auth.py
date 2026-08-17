"""Authentication for the public MCP transport."""

from __future__ import annotations

import hmac

from fastmcp.server.auth import AccessToken, TokenVerifier


class BearerTokenVerifier(TokenVerifier):
    """Validate one deployment-supplied bearer token in constant time."""

    def __init__(self, expected_token: str) -> None:
        super().__init__(required_scopes=["mcp:access"])
        self._expected_token = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token, self._expected_token):
            return None
        return AccessToken(
            token=token,
            client_id="netdisco-mcp-client",
            scopes=["mcp:access"],
            claims={"sub": "netdisco-mcp-client"},
        )
