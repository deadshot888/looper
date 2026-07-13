from __future__ import annotations

from pathlib import Path

from looper.core.command_env import build_command_env
from looper.core.config import LooperConfig
from looper.core.models import GateResult
from looper.core.process import run_command


class GateRunner:
    def __init__(self, cfg: LooperConfig):
        self.cfg = cfg

    def run_all(self, workspace: Path, experiment_id: str) -> list[GateResult]:
        results: list[GateResult] = []
        env = build_command_env(
            workspace,
            [artifact.path for artifact in self.cfg.artifacts],
            experiment_id,
            self.cfg.execution,
            {"LOOPER_SEED": str(self.cfg.search.seed)},
        )
        for gate in self.cfg.gates:
            completed = run_command(
                gate.command,
                workspace,
                env,
                float(gate.timeout_seconds),
                int(gate.max_output_chars),
            )
            results.append(
                GateResult(
                    name=gate.name,
                    passed=completed.exit_code == 0 and not completed.timed_out,
                    exit_code=completed.exit_code,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    duration_seconds=completed.duration_seconds,
                    timed_out=completed.timed_out,
                )
            )
        return results
