from __future__ import annotations

import json
import os
from pathlib import Path

artifact_paths = json.loads(os.environ["LOOPER_ARTIFACTS"])
experiment_index = int(os.environ["LOOPER_EXPERIMENT_INDEX"])
tools_path = Path(artifact_paths[0])

catalog = json.loads(tools_path.read_text(encoding="utf-8"))
tools = {tool["name"]: tool for tool in catalog["tools"]}

steps = [
    "selection_descriptions",
    "parameter_descriptions",
    "write_tool_confirmation",
]


def properties(tool_name: str) -> dict:
    return tools[tool_name]["inputSchema"].setdefault("properties", {})


for step in steps[: experiment_index % len(steps) + 1]:
    if step == "selection_descriptions":
        tools["search_deals"]["description"] = (
            "Use when the user wants to find, filter, or compare CRM deals. "
            "Do not use for changing deal data."
        )
        tools["update_deal"]["description"] = (
            "Use only when the user explicitly asks to change an existing CRM deal. "
            "Requires a known deal_id and confirmation for material updates."
        )
    elif step == "parameter_descriptions":
        properties("search_deals")["query"]["description"] = (
            "Search text such as company name, contact name, or deal keyword."
        )
        properties("search_deals")["stage"]["description"] = (
            "Optional pipeline stage filter such as prospecting, diligence, or closed."
        )
        properties("update_deal")["deal_id"]["description"] = (
            "Stable CRM deal identifier returned by search_deals or provided by the user."
        )
        properties("update_deal")["status"]["description"] = (
            "New deal status to apply after the user has confirmed the update."
        )
    elif step == "write_tool_confirmation":
        update_schema = tools["update_deal"]["inputSchema"]
        update_schema["additionalProperties"] = False
        update_schema["required"] = ["deal_id", "status", "confirmation"]
        properties("update_deal")["confirmation"] = {
            "type": "boolean",
            "description": "Must be true only after the user confirms the write action.",
        }

tools_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
print(f"updated={tools_path}")
