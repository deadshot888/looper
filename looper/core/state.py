from __future__ import annotations

import json
from pathlib import Path

from looper.core.models import State


class StateStore:
    def __init__(self, root: Path):
        self.path = root / ".looper" / "state.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> State:
        if not self.path.exists():
            return State()
        return State.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, state: State) -> None:
        self.path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
