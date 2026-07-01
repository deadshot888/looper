from __future__ import annotations

import json
import sys

import pytest

from looper.core.config import LooperConfig
from looper.core.mutator import Mutator


def test_command_mutator_runs_in_workspace(tmp_path):
    artifact = tmp_path / "schema.json"
    artifact.write_text('{"name": "demo"}', encoding="utf-8")
    script = tmp_path / "mutate.py"
    script.write_text(
        """
import json
import os
from pathlib import Path

path = Path(json.loads(os.environ["LOOPER_ARTIFACTS"])[0])
data = json.loads(path.read_text(encoding="utf-8"))
data["variant"] = int(os.environ["LOOPER_EXPERIMENT_INDEX"])
path.write_text(json.dumps(data), encoding="utf-8")
""".strip(),
        encoding="utf-8",
    )
    cfg = LooperConfig.model_validate(
        {
            "name": "command-mutator-test",
            "artifacts": [{"id": "schema", "type": "json", "path": "schema.json"}],
            "runner": {"command": "echo ok", "result_path": ".looper/result.json"},
            "mutator": {
                "provider": "command",
                "command": f'"{sys.executable}" "{script}"',
            },
        }
    )

    changed = Mutator(cfg).mutate(tmp_path, 2)

    assert changed == ["schema.json"]
    assert json.loads(artifact.read_text(encoding="utf-8"))["variant"] == 2


def test_command_mutator_requires_command(tmp_path):
    cfg = LooperConfig.model_validate(
        {
            "name": "command-mutator-test",
            "artifacts": [{"id": "schema", "type": "json", "path": "schema.json"}],
            "runner": {"command": "echo ok", "result_path": ".looper/result.json"},
            "mutator": {"provider": "command"},
        }
    )

    with pytest.raises(ValueError, match="mutator.command is required"):
        Mutator(cfg).mutate(tmp_path, 0)
