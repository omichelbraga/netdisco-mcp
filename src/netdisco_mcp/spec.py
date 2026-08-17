"""Fetch, normalize, and catalog the Netdisco Swagger specification."""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
WRITE_METHODS = {"post", "put", "patch", "delete"}


@dataclass(frozen=True, slots=True)
class Operation:
    name: str
    method: str
    path: str
    tag: str
    description: str
    mutation: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "method": self.method,
            "path": self.path,
            "tag": self.tag,
            "description": self.description,
            "mutation": self.mutation,
        }


def fetch_swagger(url: str, *, verify: bool, timeout: float) -> dict[str, Any]:
    """Retrieve the source Swagger/OpenAPI document."""
    with httpx.Client(verify=verify, timeout=timeout, follow_redirects=True) as client:
        response = client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        value = response.json()
    if not isinstance(value, dict):
        raise ValueError("Netdisco specification was not a JSON object")
    return value


def _list(value: Any, fallback: str) -> list[str]:
    if value is None:
        return [fallback]
    if isinstance(value, str):
        return [value]
    return list(value)


def _rewrite_refs(value: Any) -> Any:
    if isinstance(value, dict):
        rewritten: dict[str, Any] = {}
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str):
                item = item.replace("#/definitions/", "#/components/schemas/")
                item = item.replace("#/parameters/", "#/components/parameters/")
                item = item.replace("#/responses/", "#/components/responses/")
            rewritten[key] = _rewrite_refs(item)
        return rewritten
    if isinstance(value, list):
        return [_rewrite_refs(item) for item in value]
    return value


def _sanitize_schema(value: Any) -> Any:
    """Repair Swagger schema shapes that are invalid in OpenAPI 3.

    Netdisco marks individual object properties with ``required: 0|1``.
    OpenAPI 3 requires a list of property names on the containing object.
    """
    if isinstance(value, list):
        return [_sanitize_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    result = {
        key: _sanitize_schema(item)
        for key, item in value.items()
        if key != "properties"
    }
    properties = value.get("properties")
    if isinstance(properties, dict):
        required_names: list[str] = []
        cleaned_properties: dict[str, Any] = {}
        for name, property_schema in properties.items():
            if isinstance(property_schema, dict):
                property_schema = dict(property_schema)
                required_flag = property_schema.pop("required", None)
                if required_flag in {True, 1, "1", "true"}:
                    required_names.append(name)
            cleaned_properties[name] = _sanitize_schema(property_schema)
        result["properties"] = cleaned_properties

        existing_required = result.get("required")
        if not isinstance(existing_required, list):
            existing_required = []
        merged_required = list(dict.fromkeys([*existing_required, *required_names]))
        if merged_required:
            result["required"] = merged_required
        elif "required" in result and not isinstance(result["required"], list):
            result.pop("required", None)
    elif "required" in result and not isinstance(result["required"], list):
        result.pop("required", None)

    if result.get("type") == "array" and result.get("default") == "[]":
        result["default"] = []
    if result.get("type") == "boolean" and isinstance(result.get("default"), str):
        default_key = result["default"].strip().lower()
        if default_key in {"true", "false"}:
            result["default"] = default_key == "true"
    if result.get("type") == "integer" and isinstance(result.get("default"), str):
        try:
            result["default"] = int(result["default"])
        except ValueError:
            pass
    return result


def _schema_for_parameter(parameter: dict[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(parameter.get("schema") or {})
    for key in (
        "type",
        "format",
        "items",
        "default",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
    ):
        if key in parameter and key not in schema:
            schema[key] = copy.deepcopy(parameter[key])
    return _sanitize_schema(_rewrite_refs(schema))


def _convert_parameter(parameter: dict[str, Any]) -> dict[str, Any]:
    """Move Swagger 2 parameter type fields into an OpenAPI 3 schema."""
    result = _rewrite_refs(copy.deepcopy(parameter))
    if "$ref" in result:
        return result
    result["schema"] = _schema_for_parameter(result)
    for key in (
        "type",
        "format",
        "items",
        "default",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
        "collectionFormat",
    ):
        result.pop(key, None)
    if "required" in result:
        result["required"] = bool(result["required"])
    return result


def _convert_operation(
    operation: dict[str, Any],
    *,
    consumes: list[str],
    produces: list[str],
) -> dict[str, Any]:
    result = _rewrite_refs(copy.deepcopy(operation))
    parameters = []
    body_parameter = None
    form_parameters = []
    for parameter in result.pop("parameters", []):
        location = parameter.get("in")
        if location == "body":
            body_parameter = parameter
        elif location == "formData":
            form_parameters.append(parameter)
        else:
            parameters.append(_convert_parameter(parameter))
    if parameters:
        result["parameters"] = parameters

    if body_parameter is not None:
        result["requestBody"] = {
            "required": bool(body_parameter.get("required", False)),
            "description": body_parameter.get("description", "JSON request body"),
            "content": {
                media_type: {"schema": _schema_for_parameter(body_parameter)}
                for media_type in consumes
            },
        }
    elif form_parameters:
        properties = {p["name"]: _schema_for_parameter(p) for p in form_parameters}
        required = [p["name"] for p in form_parameters if p.get("required")]
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        result["requestBody"] = {
            "content": {media_type: {"schema": schema} for media_type in consumes}
        }

    converted_responses: dict[str, Any] = {}
    for status, response in result.get("responses", {}).items():
        response = copy.deepcopy(response)
        schema = response.pop("schema", None)
        if schema is not None:
            response["content"] = {
                media_type: {"schema": _sanitize_schema(_rewrite_refs(schema))}
                for media_type in produces
            }
        response.setdefault("description", "Netdisco API response")
        converted_responses[str(status)] = response
    result["responses"] = converted_responses or {
        "default": {"description": "Netdisco API response"}
    }
    result.pop("consumes", None)
    result.pop("produces", None)
    result.pop("schemes", None)
    return result


def _words(path: str) -> list[str]:
    words = []
    for part in path.strip("/").split("/"):
        if part in {"api", "v1", "object"} or (part.startswith("{") and part.endswith("}")):
            continue
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", part).strip("_").lower()
        if cleaned:
            words.append(cleaned)
    return words


def _friendly_operation_id(method: str, path: str) -> str:
    words = _words(path)
    if not words:
        words = ["root"]
    if words[0] == "search":
        prefix = "search"
        words = words[1:]
    elif method == "get":
        prefix = "get"
    elif method == "post":
        prefix = "create"
    elif method in {"put", "patch"}:
        prefix = "update"
    elif method == "delete":
        prefix = "delete"
    else:
        prefix = method
    return "_".join([prefix, *words])


def _assign_operation_ids(spec: dict[str, Any]) -> None:
    seen: set[str] = set()
    for path in sorted(spec.get("paths", {})):
        item = spec["paths"][path]
        for method in sorted(HTTP_METHODS):
            operation = item.get(method)
            if not isinstance(operation, dict):
                continue
            candidate = _friendly_operation_id(method, path)
            if candidate in seen:
                digest = hashlib.sha1(f"{method}:{path}".encode()).hexdigest()[:7]
                candidate = f"{candidate}_{digest}"
            seen.add(candidate)
            operation["operationId"] = candidate
            description = operation.get("description") or operation.get("summary") or ""
            operation["description"] = (
                f"{description.strip()}\n\nNetdisco API route: {method.upper()} {path}"
            ).strip()


def normalize_spec(
    source: dict[str, Any],
    *,
    base_url: str,
    read_only: bool = False,
) -> dict[str, Any]:
    """Return an OpenAPI 3 document suitable for FastMCP.

    Netdisco 2.101 exposes Swagger 2.0. FastMCP consumes OpenAPI 3, so this
    converter upgrades the constructs used by Netdisco while retaining every
    operation and parameter.
    """
    if str(source.get("openapi", "")).startswith("3."):
        result = _rewrite_refs(copy.deepcopy(source))
        result["servers"] = [{"url": base_url.rstrip("/")}]
    elif source.get("swagger") == "2.0":
        consumes = _list(source.get("consumes"), "application/json")
        produces = _list(source.get("produces"), "application/json")
        components: dict[str, Any] = {
            "schemas": _sanitize_schema(
                _rewrite_refs(copy.deepcopy(source.get("definitions", {})))
            ),
            "securitySchemes": _rewrite_refs(
                copy.deepcopy(source.get("securityDefinitions", {}))
            ),
        }
        if source.get("parameters"):
            components["parameters"] = _rewrite_refs(copy.deepcopy(source["parameters"]))
        if source.get("responses"):
            components["responses"] = _rewrite_refs(copy.deepcopy(source["responses"]))

        paths: dict[str, Any] = {}
        for path, path_item in source.get("paths", {}).items():
            converted_item: dict[str, Any] = {}
            for key, value in path_item.items():
                if key.lower() in HTTP_METHODS and isinstance(value, dict):
                    converted_item[key.lower()] = _convert_operation(
                        value,
                        consumes=_list(value.get("consumes"), consumes[0]),
                        produces=_list(value.get("produces"), produces[0]),
                    )
                elif key == "parameters" and isinstance(value, list):
                    converted_item[key] = [_convert_parameter(item) for item in value]
                else:
                    converted_item[key] = _rewrite_refs(copy.deepcopy(value))
            paths[path] = converted_item

        result = {
            "openapi": "3.0.3",
            "info": copy.deepcopy(source.get("info") or {"title": "Netdisco", "version": "unknown"}),
            "servers": [{"url": base_url.rstrip("/")}],
            "paths": paths,
            "components": components,
        }
        if source.get("security"):
            result["security"] = copy.deepcopy(source["security"])
        if source.get("tags"):
            result["tags"] = copy.deepcopy(source["tags"])
    else:
        raise ValueError("Expected a Swagger 2.0 or OpenAPI 3.x document")

    if read_only:
        for path_item in result.get("paths", {}).values():
            for method in list(path_item):
                if method.lower() in WRITE_METHODS:
                    del path_item[method]

    _assign_operation_ids(result)
    return result


def iter_operations(spec: dict[str, Any]) -> Iterable[Operation]:
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            method_lower = method.lower()
            if method_lower not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            tags = operation.get("tags") or ["Untagged"]
            yield Operation(
                name=operation["operationId"],
                method=method_upper(method_lower),
                path=path,
                tag=str(tags[0]),
                description=str(operation.get("description") or "").split("\n\n", 1)[0],
                mutation=method_lower in WRITE_METHODS,
            )


def method_upper(method: str) -> str:
    return method.upper()


def search_operations(
    operations: Iterable[Operation],
    *,
    query: str = "",
    tag: str | None = None,
    method: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    needle = query.casefold().strip()
    tag_key = tag.casefold().strip() if tag else None
    method_key = method.upper().strip() if method else None
    matches = []
    for operation in operations:
        haystack = " ".join(
            [operation.name, operation.method, operation.path, operation.tag, operation.description]
        ).casefold()
        if needle and needle not in haystack:
            continue
        if tag_key and operation.tag.casefold() != tag_key:
            continue
        if method_key and operation.method != method_key:
            continue
        matches.append(operation.as_dict())
        if len(matches) >= max(1, min(limit, 100)):
            break
    return matches
