import pytest

from netdisco_mcp.config import Settings


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("stdio", "stdio"),
        ("stdin", "stdio"),
        ("streamable-http", "streamable-http"),
        ("streamable_http", "streamable-http"),
        ("http", "streamable-http"),
    ],
)
def test_transport_aliases(monkeypatch, configured, expected):
    monkeypatch.setenv("NETDISCO_URL", "https://netdisco.example.net")
    monkeypatch.setenv("NETDISCO_MCP_TRANSPORT", configured)
    assert Settings.from_env().transport == expected
