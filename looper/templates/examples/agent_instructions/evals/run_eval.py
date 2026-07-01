from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path.cwd()
INSTRUCTIONS = ROOT / "examples" / "agent_instructions" / "instructions" / "AGENTS.md"
RESULT_PATH = Path(os.environ.get("LOOPER_RESULT_PATH", ROOT / ".looper" / "result.json"))

text = INSTRUCTIONS.read_text(encoding="utf-8").lower()

checks = {
    "cites_sources": "cite the policy" in text or "cite the source" in text,
    "asks_clarifying_question": "clarifying question" in text,
    "does_not_invent": "do not invent" in text,
    "escalates_when_unsure": "escalate" in text,
}

score = sum(1 for passed in checks.values() if passed) / len(checks)

RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
RESULT_PATH.write_text(
    json.dumps(
        {
            "score": score,
            "metrics": checks,
            "notes": "Toy deterministic eval for markdown agent instructions.",
        },
        indent=2,
    ),
    encoding="utf-8",
)

print(f"score={score}")
