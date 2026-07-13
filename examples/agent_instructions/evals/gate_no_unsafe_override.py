from __future__ import annotations

from pathlib import Path

instructions = (
    Path("examples/agent_instructions/instructions/AGENTS.md")
    .read_text(
        encoding="utf-8",
    )
    .lower()
)

forbidden = ["ignore safety", "ignore policy", "bypass approval", "disable gates"]

if any(term in instructions for term in forbidden):
    raise SystemExit(1)

raise SystemExit(0)
