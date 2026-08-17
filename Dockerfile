FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV NETDISCO_MCP_TRANSPORT=streamable-http \
    NETDISCO_MCP_HTTP_HOST=0.0.0.0 \
    NETDISCO_MCP_HTTP_PORT=8000

EXPOSE 8000
ENTRYPOINT ["netdisco-mcp"]
