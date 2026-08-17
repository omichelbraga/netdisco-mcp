"""Environment-driven server configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved Netdisco and MCP settings."""

    netdisco_url: str
    spec_url: str
    api_token: str | None
    auth_scheme: str
    username: str | None
    password: str | None
    tls_verify: bool
    request_timeout: float
    read_only: bool
    guidance_gate: bool
    guidance_ttl: int
    max_response_chars: int
    transport: str
    http_host: str
    http_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        url = os.getenv("NETDISCO_URL", "").strip().rstrip("/")
        if not url:
            raise ValueError("NETDISCO_URL is required, for example https://netdisco.example.net")

        spec_url = os.getenv("NETDISCO_SPEC_URL", f"{url}/swagger.json").strip()
        auth_scheme = os.getenv("NETDISCO_AUTH_SCHEME", "Bearer").strip()
        transport = os.getenv("NETDISCO_MCP_TRANSPORT", "stdio").strip().lower()
        transport = {
            "stdin": "stdio",
            "http": "streamable-http",
            "streamable_http": "streamable-http",
        }.get(transport, transport)
        if transport not in {"stdio", "streamable-http"}:
            raise ValueError(
                "NETDISCO_MCP_TRANSPORT must be stdio or streamable-http "
                "(stdin and http are accepted aliases)"
            )

        return cls(
            netdisco_url=url,
            spec_url=spec_url,
            api_token=os.getenv("NETDISCO_API_TOKEN") or None,
            auth_scheme=auth_scheme,
            username=os.getenv("NETDISCO_USERNAME") or None,
            password=os.getenv("NETDISCO_PASSWORD") or None,
            tls_verify=_bool("NETDISCO_TLS_VERIFY", True),
            request_timeout=float(os.getenv("NETDISCO_TIMEOUT", "30")),
            read_only=_bool("NETDISCO_READ_ONLY", False),
            guidance_gate=_bool("NETDISCO_GUIDANCE_GATE", True),
            guidance_ttl=_int("NETDISCO_GUIDANCE_TTL", 1800),
            max_response_chars=_int("NETDISCO_MAX_RESPONSE_CHARS", 50_000),
            transport=transport,
            http_host=os.getenv("NETDISCO_MCP_HTTP_HOST", "127.0.0.1"),
            http_port=_int("NETDISCO_MCP_HTTP_PORT", 8000),
        )

    def authorization_header(self) -> str | None:
        if not self.api_token:
            return None
        if self.auth_scheme.lower() in {"", "raw", "none"}:
            return self.api_token
        return f"{self.auth_scheme} {self.api_token}"
