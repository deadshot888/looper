from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path.cwd()
TOOLS = ROOT / "examples" / "mcp_tool_selection" / "server" / "tools.json"
RESULT_PATH = Path(os.environ.get("LOOPER_RESULT_PATH", ROOT / ".looper" / "result.json"))

catalog = json.loads(TOOLS.read_text(encoding="utf-8"))
tools = {tool["name"]: tool for tool in catalog.get("tools", [])}


def description(tool_name: str) -> str:
    return tools.get(tool_name, {}).get("description", "").lower()


def props(tool_name: str) -> dict:
    schema = tools.get(tool_name, {}).get("inputSchema", {})
    return schema.get("properties", {})


def required(tool_name: str) -> list[str]:
    schema = tools.get(tool_name, {}).get("inputSchema", {})
    return schema.get("required", [])


search_description = description("search_deals")
update_description = description("update_deal")
search_props = props("search_deals")
update_props = props("update_deal")

all_parameter_descriptions = [
    field.get("description", "")
    for field in [*search_props.values(), *update_props.values()]
]

checks = {
    "selection_guidance_for_search": "use when" in search_description and "do not use" in search_description,
    "selection_guidance_for_update": "use only" in update_description and "confirmation" in update_description,
    "parameters_are_described": all(len(text) >= 20 for text in all_parameter_descriptions),
    "write_tool_requires_confirmation": "confirmation" in required("update_deal"),
}

score = sum(1 for passed in checks.values() if passed) / len(checks)

RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
RESULT_PATH.write_text(
    json.dumps(
        {
            "score": score,
            "metrics": checks,
            "notes": "Toy deterministic eval for MCP tool-selection and schema quality.",
        },
        indent=2,
    ),
    encoding="utf-8",
)

print(f"score={score}")
