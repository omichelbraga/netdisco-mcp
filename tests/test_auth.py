import pytest

from netdisco_mcp.auth import BearerTokenVerifier


@pytest.mark.asyncio
async def test_bearer_token_verifier_accepts_only_exact_token():
    verifier = BearerTokenVerifier("correct-token")

    accepted = await verifier.verify_token("correct-token")
    rejected = await verifier.verify_token("wrong-token")

    assert accepted is not None
    assert accepted.client_id == "netdisco-mcp-client"
    assert accepted.scopes == ["mcp:access"]
    assert rejected is None
