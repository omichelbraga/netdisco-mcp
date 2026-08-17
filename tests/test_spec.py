from netdisco_mcp.spec import iter_operations, normalize_spec, search_operations


SOURCE = {
    "swagger": "2.0",
    "info": {"title": "App::Netdisco", "version": "2.101000"},
    "produces": ["application/json"],
    "consumes": ["application/json"],
    "securityDefinitions": {
        "APIKeyHeader": {"type": "apiKey", "in": "header", "name": "Authorization"}
    },
    "security": [{"APIKeyHeader": []}],
    "paths": {
        "/api/v1/search/device": {
            "get": {
                "tags": ["Search"],
                "description": "Device Search",
                "parameters": [{"name": "q", "in": "query", "type": "string"}],
                "responses": {"default": {"description": "ok"}},
            }
        },
        "/api/v1/object/device/{ip}": {
            "get": {
                "tags": ["Objects"],
                "description": "Get device",
                "parameters": [
                    {"name": "ip", "in": "path", "required": True, "type": "string"}
                ],
                "responses": {"default": {"description": "ok"}},
            }
        },
        "/api/v1/queue/jobs": {
            "post": {
                "tags": ["Queue"],
                "description": "Submit jobs",
                "parameters": [
                    {
                        "name": "jobs",
                        "in": "body",
                        "schema": {"type": "array", "items": {"type": "object"}},
                    }
                ],
                "responses": {"default": {"description": "ok"}},
            }
        },
    },
}


def test_swagger_is_upgraded_and_all_operations_are_named():
    spec = normalize_spec(SOURCE, base_url="https://netdisco.example.net")
    assert spec["openapi"] == "3.0.3"
    assert spec["servers"] == [{"url": "https://netdisco.example.net"}]
    search_parameter = spec["paths"]["/api/v1/search/device"]["get"]["parameters"][0]
    assert search_parameter["schema"]["type"] == "string"
    assert "type" not in search_parameter
    operations = list(iter_operations(spec))
    assert [item.name for item in operations] == [
        "search_device",
        "get_device",
        "create_queue_jobs",
    ]
    assert spec["paths"]["/api/v1/queue/jobs"]["post"]["requestBody"]


def test_invalid_property_required_flags_are_hoisted():
    source = dict(SOURCE)
    source["paths"] = {
        "/api/v1/queue/jobs": {
            "post": {
                "tags": ["Queue"],
                "parameters": [
                    {
                        "name": "jobs",
                        "in": "body",
                        "schema": {
                            "type": "array",
                            "default": "[]",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {"type": "string", "required": 1},
                                    "device": {"type": "string", "required": 0},
                                },
                            },
                        },
                    }
                ],
                "responses": {"default": {"description": "ok"}},
            }
        }
    }
    spec = normalize_spec(source, base_url="https://netdisco.example.net")
    schema = spec["paths"]["/api/v1/queue/jobs"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert schema["default"] == []
    assert schema["items"]["required"] == ["action"]
    assert "required" not in schema["items"]["properties"]["device"]


def test_read_only_removes_mutations_only():
    spec = normalize_spec(SOURCE, base_url="https://netdisco.example.net", read_only=True)
    operations = list(iter_operations(spec))
    assert len(operations) == 2
    assert all(not operation.mutation for operation in operations)


def test_capability_search_is_compact_and_filterable():
    spec = normalize_spec(SOURCE, base_url="https://netdisco.example.net")
    matches = search_operations(iter_operations(spec), query="device", method="GET")
    assert [item["tool"] for item in matches] == ["search_device", "get_device"]


def test_string_defaults_are_coerced_to_declared_types():
    source = dict(SOURCE)
    source["paths"] = {
        "/api/v1/search/node": {
            "get": {
                "tags": ["Search"],
                "parameters": [
                    {
                        "name": "partial",
                        "in": "query",
                        "type": "boolean",
                        "default": "false",
                    }
                ],
                "responses": {"default": {"description": "ok"}},
            }
        }
    }
    spec = normalize_spec(source, base_url="https://netdisco.example.net")
    parameter = spec["paths"]["/api/v1/search/node"]["get"]["parameters"][0]
    assert parameter["schema"]["default"] is False
