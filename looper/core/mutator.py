from __future__ import annotations

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
        changed: list[str] = []
        for artifact in self.cfg.artifacts:
            changed.extend(self._mutate_artifact(workspace, artifact, experiment_index))
        return changed

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
