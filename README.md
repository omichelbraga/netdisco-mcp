# Netdisco MCP

An agent-friendly MCP server that exposes **every operation** advertised by a
Netdisco instance's `swagger.json`.

Unlike a handwritten subset, the tool surface is generated at startup. The
server upgrades Netdisco's Swagger 2.0 document to OpenAPI 3, assigns stable
human-readable tool names, and feeds the result to FastMCP.

## Agent experience

The first tool is `get_guidance`, backed by the bundled operating guide. The
server's initialization instructions tell agents to call it first, and an
optional Portainer-style guidance gate delivers the guide when an agent skips
that step. `find_capability` searches the full tool catalog without guessing.

With Netdisco 2.101000, the observed surface is:

- 79 generated API tools
- 72 GET tools
- 7 mutation tools
- 2 agent-assistance tools (`get_guidance`, `find_capability`)

Counts track the connected instance and can change when Netdisco changes its
Swagger document.

## Configure

Copy `.env.example` to `.env` and set at least:

```dotenv
NETDISCO_URL=https://netdisco.example.net
NETDISCO_API_TOKEN=your-permanent-api-token
```

Important settings:

| Setting | Default | Purpose |
|---|---:|---|
| `NETDISCO_SPEC_URL` | `$NETDISCO_URL/swagger.json` | Override the live specification URL |
| `NETDISCO_AUTH_SCHEME` | `Bearer` | Use `raw` for an unprefixed Authorization value |
| `NETDISCO_TLS_VERIFY` | `1` | Validate the Netdisco TLS certificate |
| `NETDISCO_READ_ONLY` | `0` | Set to `1` to remove POST/PUT/PATCH/DELETE tools |
| `NETDISCO_GUIDANCE_GATE` | `1` | Require guidance once per activity window |
| `NETDISCO_GUIDANCE_TTL` | `1800` | Guidance activity window in seconds |
| `NETDISCO_MAX_RESPONSE_CHARS` | `50000` | Protect agent context from oversized responses |
| `NETDISCO_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` (`stdin`/`http` aliases work) |

Basic authentication is also supported with `NETDISCO_USERNAME` and
`NETDISCO_PASSWORD`.

## Transports

Both requested MCP transports are supported:

- **stdio** — the MCP process communicates over standard input/output. This is
  the default and is best for Codex, Claude Desktop, and other local clients.
- **Streamable HTTP** — the MCP server listens at `http://HOST:PORT/mcp`. This
  is best for remote clients and shared deployments.

One process serves one transport. To make both available at the same time,
run two processes with the same Netdisco configuration and different
`NETDISCO_MCP_TRANSPORT` values.

## Run with stdio

```bash
uv sync --extra dev
uv run netdisco-mcp --check
uv run netdisco-mcp
```

Example MCP client configuration:

```json
{
  "mcpServers": {
    "netdisco": {
      "command": "uv",
      "args": ["--directory", "/path/to/netdisco-mcp", "run", "netdisco-mcp"],
      "env": {
        "NETDISCO_URL": "https://netdisco.example.net",
        "NETDISCO_API_TOKEN": "replace-me"
      }
    }
  }
}
```

## Run with Streamable HTTP

```bash
NETDISCO_MCP_TRANSPORT=streamable-http \
NETDISCO_MCP_HTTP_HOST=127.0.0.1 \
NETDISCO_MCP_HTTP_PORT=8000 \
uv run netdisco-mcp
```

The MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

Example remote-client registration:

```bash
claude mcp add netdisco \
  --transport http http://127.0.0.1:8000/mcp
```

## Container

```bash
docker compose up --build -d
```

The supplied Compose file runs Streamable HTTP and only publishes it on
localhost. Put a properly authenticated TLS reverse proxy in front of it for
shared use. Do not publish an unauthenticated MCP endpoint containing
network-management tools to the public internet.

## Tool naming examples

- `GET /api/v1/search/device` becomes `search_device`
- `GET /api/v1/object/device/{ip}/ports` becomes `get_device_ports`
- `GET /api/v1/report/device/deviceinventory` becomes
  `get_report_device_deviceinventory`
- `POST /api/v1/queue/jobs` becomes `create_queue_jobs`
- `DELETE /api/v1/queue/jobs` becomes `delete_queue_jobs`

Every generated tool description retains its original Netdisco description
and exact HTTP route.

## Safety posture

Full API coverage is enabled by default, including mutations. For exploratory
or broadly shared deployments, set `NETDISCO_READ_ONLY=1`. Netdisco's own
credential permissions remain authoritative in either mode.

## Development

```bash
uv run pytest
```

The tests verify Swagger-to-OpenAPI conversion, stable operation naming,
complete operation retention, request-body conversion, read-only filtering,
and capability discovery.

## License

MIT
