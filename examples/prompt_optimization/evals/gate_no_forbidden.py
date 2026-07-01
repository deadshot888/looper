from __future__ import annotations

from pathlib import Path

prompt = Path("examples/prompt_optimization/prompts/support_agent.md").read_text(encoding="utf-8").lower()

forbidden = ["ignore policy", "make up facts", "bypass approval"]

if any(term in prompt for term in forbidden):
    raise SystemExit(1)

raise SystemExit(0)
