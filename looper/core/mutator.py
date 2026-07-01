from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from looper.core.config import ArtifactConfig, LooperConfig


STUB_IMPROVEMENTS = [
    "\n\nWhen answering, cite the policy or source used.",
    "\n\nIf key information is missing, ask a clarifying question.",
    "\n\nDo not invent facts that are not present in the context.",
    "\n\nEscalate when unsure or when the request is high risk.",
]


class Mutator:
    def __init__(self, cfg: LooperConfig):
        self.cfg = cfg

    def mutate(self, workspace: Path, experiment_index: int) -> list[str]:
        if self.cfg.mutator.provider == "command":
            return self._mutate_with_command(workspace, experiment_index)

        changed: list[str] = []
        for artifact in self.cfg.artifacts:
            changed.extend(self._mutate_artifact(workspace, artifact, experiment_index))
        return changed

    def _mutate_with_command(self, workspace: Path, experiment_index: int) -> list[str]:
        if not self.cfg.mutator.command:
            raise ValueError("mutator.command is required when mutator.provider is 'command'.")

        artifact_paths = [artifact.path for artifact in self.cfg.artifacts]
        env = os.environ.copy()
        env["LOOPER_EXPERIMENT_INDEX"] = str(experiment_index)
        env["LOOPER_ARTIFACTS"] = json.dumps(artifact_paths)
        env["LOOPER_WORKSPACE"] = str(workspace)
        env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"

        completed = subprocess.run(
            self.cfg.mutator.command,
            shell=True,
            cwd=str(workspace),
            env=env,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Mutator command failed with exit code {completed.returncode}\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        return artifact_paths

    def _mutate_artifact(
        self,
        workspace: Path,
        artifact: ArtifactConfig,
        experiment_index: int,
    ) -> list[str]:
        path = workspace / artifact.path
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found in workspace: {artifact.path}")

        if self.cfg.mutator.provider == "stub":
            text = path.read_text(encoding="utf-8")
            count = experiment_index % len(STUB_IMPROVEMENTS) + 1
            additions = STUB_IMPROVEMENTS[:count]
            changed = False
            for addition in additions:
                if addition.strip() not in text:
                    text = text.rstrip() + addition + "\n"
                    changed = True
            if changed:
                path.write_text(text, encoding="utf-8")
            return [artifact.path]

        raise NotImplementedError(
            f"Mutator provider {self.cfg.mutator.provider!r} is not implemented in V0 starter."
        )
