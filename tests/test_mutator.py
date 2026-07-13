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
Path(os.environ["LOOPER_MUTATION_META_PATH"]).write_text(
    json.dumps({
        "hypothesis": "Adding a variant marker improves schema traceability.",
        "changes": ["Added variant marker to schema.json."],
    }),
    encoding="utf-8",
)
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

    result = Mutator(cfg).mutate(tmp_path, 2)

    assert result.artifacts == ["schema.json"]
    assert result.hypothesis == "Adding a variant marker improves schema traceability."
    assert result.change_summary == "Added variant marker to schema.json."
    assert json.loads(artifact.read_text(encoding="utf-8"))["variant"] == 2


def test_command_mutator_requires_command(tmp_path):
    with pytest.raises(ValueError, match="mutator.command is required"):
        LooperConfig.model_validate(
            {
                "name": "command-mutator-test",
                "artifacts": [{"id": "schema", "type": "json", "path": "schema.json"}],
                "runner": {"command": "echo ok", "result_path": ".looper/result.json"},
                "mutator": {"provider": "command"},
            }
        )
