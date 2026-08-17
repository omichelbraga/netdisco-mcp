# Netdisco MCP operating guide

This MCP server exposes the complete REST API advertised by the connected
Netdisco instance. The API surface is generated at startup, so tool coverage
tracks the server's own `swagger.json` instead of a stale handwritten subset.

## Required first step

Call `get_guidance` once at the start of a Netdisco task. If you skip it, the
guidance gate returns this guide and asks you to retry. Use `find_capability`
when the right endpoint is unclear; do not guess tool names.

## Tool families

- `search_*`: locate devices, nodes, ports, or VLANs. Start here when the user
  gives a hostname, IP address, MAC address, interface description, or VLAN.
- `get_device*`: inspect a known device and its ports, neighbors, VLANs,
  modules, power information, wireless interfaces, SSIDs, logs, or nodes.
- `get_report_*`: fleet-wide inventories and exception reports. Reports may be
  large; prefer a search or object endpoint when the question is specific.
- `get_queue*`: inspect Netdisco backend and job state.
- `create_*`, `update_*`, `delete_*`: mutations. They are absent when
  `NETDISCO_READ_ONLY=1`.

## Core workflows

### Find where an endpoint is connected

1. Use `search_node` with the IP, hostname, or MAC address.
2. Read the returned device IP and port identifier.
3. Use `get_device_port` or `get_device_port_nodes` for authoritative port
   context.
4. If the result looks like an uplink, inspect `get_device_port_neighbor` and
   continue only as needed.

### Inspect a switch

1. Resolve it with `search_device` if the management IP is not known.
2. Use `get_device` for the device record.
3. Use `get_device_ports` for interfaces and operational state.
4. Add targeted calls for neighbors, VLANs, power, modules, or wireless data.

### Inventory or compliance questions

Use the closest report tool, such as device, IP, VLAN, PoE, duplex mismatch,
error-disabled, administratively down, or missing-model/OS reports. State the
filters and time range used. Do not treat an empty response as proof of absence
until the endpoint's required parameters have been checked.

## Result hygiene

- Prefer the narrowest endpoint and query that answers the question.
- Avoid requesting every device's ports when one report or search is enough.
- Preserve exact IP addresses, MAC addresses, VLAN IDs, and interface names.
- Distinguish current/active nodes from historical nodes and include age data
  when the question depends on recency.
- A down device can have stale inventory. Report reachability separately from
  last-discovered data.
- Responses are capped to protect agent context. If truncation occurs, narrow
  the request rather than repeating the same call.

## Mutation safety

Write operations can affect live network operations. Before a mutation:

1. Inspect current state using a read tool.
2. Resolve the exact device and port; never mutate a fuzzy search result.
3. Explain the intended change and blast radius.
4. Obtain the user's explicit confirmation when the client policy requires it.
5. Make one mutation call.
6. Verify the resulting state with an independent read call.

Do not blindly retry a POST, PUT, or DELETE after a timeout. The request may
have reached Netdisco even if the response was lost. Verify queue and object
state first to avoid duplicate jobs or repeated changes.

## Authentication and permissions

The MCP server passes its configured Netdisco authorization to the API.
Netdisco remains the authority on what the credential may read or change. A
403 means the capability exists but the configured identity is not permitted;
do not work around it with another endpoint.

## Interpreting failures

- 400: check required or malformed parameters.
- 401: the configured Netdisco credential is missing or invalid.
- 403: the identity lacks permission for that action.
- 404: the object or endpoint may not exist on this Netdisco version.
- 409: re-read current state before deciding whether to retry.
- 5xx or timeout on reads: retry cautiously once if appropriate.
- 5xx or timeout on writes: verify state before any retry.

