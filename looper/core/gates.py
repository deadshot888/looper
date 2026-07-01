from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from looper.core.config import LooperConfig
from looper.core.models import GateResult


class GateRunner:
    def __init__(self, cfg: LooperConfig):
        self.cfg = cfg

    def run_all(self, workspace: Path, experiment_id: str) -> list[GateResult]:
        results: list[GateResult] = []
        env = os.environ.copy()
        env["LOOPER_EXPERIMENT_ID"] = experiment_id
        env["LOOPER_ARTIFACTS"] = json.dumps([a.path for a in self.cfg.artifacts])
        env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"

        for gate in self.cfg.gates:
            completed = subprocess.run(
                gate.command,
                shell=True,
                cwd=str(workspace),
                env=env,
                capture_output=True,
                text=True,
            )
            results.append(
                GateResult(
                    name=gate.name,
                    passed=completed.returncode == 0,
                    exit_code=completed.returncode,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                )
            )
        return results
