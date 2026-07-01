from __future__ import annotations

import json
from pathlib import Path

catalog = json.loads(
    Path("examples/mcp_tool_selection/server/tools.json").read_text(encoding="utf-8"),
)

tools = catalog.get("tools")
if not isinstance(tools, list) or not tools:
    raise SystemExit("MCP catalog must include a non-empty tools list.")

names: set[str] = set()
for tool in tools:
    name = tool.get("name")
    if not isinstance(name, str) or not name:
        raise SystemExit("Every MCP tool must include a name.")
    if name in names:
        raise SystemExit(f"Duplicate MCP tool name: {name}")
    names.add(name)

    if not isinstance(tool.get("description"), str) or not tool["description"]:
        raise SystemExit(f"MCP tool must include a description: {name}")

    schema = tool.get("inputSchema")
    if not isinstance(schema, dict):
        raise SystemExit(f"MCP tool must include inputSchema: {name}")
    if schema.get("type") != "object":
        raise SystemExit(f"MCP inputSchema must be an object: {name}")
    if not isinstance(schema.get("properties"), dict):
        raise SystemExit(f"MCP inputSchema must include properties: {name}")
    if not isinstance(schema.get("required", []), list):
        raise SystemExit(f"MCP inputSchema required must be a list: {name}")

raise SystemExit(0)
