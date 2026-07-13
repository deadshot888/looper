from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from looper.core.command_env import build_command_env
from looper.core.config import ArtifactConfig, LooperConfig
from looper.core.errors import CommandTimeoutError
from looper.core.integrity import file_hash
from looper.core.process import run_command

STUB_IMPROVEMENTS = [
    "\n\nWhen answering, cite the policy or source used.",
    "\n\nIf key information is missing, ask a clarifying question.",
    "\n\nDo not invent facts that are not present in the context.",
    "\n\nEscalate when unsure or when the request is high risk.",
]


@dataclass
class MutationResult:
    artifacts: list[str]
    hypothesis: str
    change_summary: str


class Mutator:
    def __init__(self, cfg: LooperConfig):
        self.cfg = cfg

    def mutate(self, workspace: Path, experiment_index: int) -> MutationResult:
        if self.cfg.mutator.provider == "command":
            return self._mutate_with_command(workspace, experiment_index)

        changed: list[str] = []
        summaries: list[str] = []
        for artifact in self.cfg.artifacts:
            artifact_changes = self._mutate_artifact(workspace, artifact, experiment_index)
            changed.extend(artifact_changes)
            if artifact_changes:
                summaries.append(f"Updated {artifact.path} with built-in guidance variant.")
        return MutationResult(
            artifacts=changed,
            hypothesis=self._stub_hypothesis(experiment_index),
            change_summary=" ".join(summaries) or "No artifact changes were produced.",
        )

    def _mutate_with_command(self, workspace: Path, experiment_index: int) -> MutationResult:
        if not self.cfg.mutator.command:
            raise ValueError("mutator.command is required when mutator.provider is 'command'.")

        artifact_paths = [artifact.path for artifact in self.cfg.artifacts]
        before_hashes = {path: file_hash(workspace / path) for path in artifact_paths}
        metadata_path = workspace / ".looper" / "mutation.json"
        if metadata_path.exists():
            metadata_path.unlink()
        env = build_command_env(
            workspace,
            artifact_paths,
            f"exp_{experiment_index + 1:04d}",
            self.cfg.execution,
            {
                "LOOPER_EXPERIMENT_INDEX": str(experiment_index),
                "LOOPER_MUTATION_META_PATH": str(metadata_path),
                "LOOPER_WORKSPACE": str(workspace),
            },
        )

        completed = run_command(
            self.cfg.mutator.command,
            workspace,
            env,
            float(self.cfg.mutator.timeout_seconds),
            int(self.cfg.mutator.max_output_chars),
        )
        if completed.timed_out:
            raise CommandTimeoutError(
                f"Mutator command timed out after {self.cfg.mutator.timeout_seconds:g} seconds."
            )
        if completed.exit_code != 0:
            raise RuntimeError(
                f"Mutator command failed with exit code {completed.exit_code}\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        metadata = self._read_metadata(metadata_path)
        metadata_artifacts = metadata.get("artifacts")
        if metadata_artifacts is not None:
            if not isinstance(metadata_artifacts, list):
                raise ValueError("Mutator metadata 'artifacts' must be a list")
            unknown = sorted(set(str(path) for path in metadata_artifacts) - set(artifact_paths))
            if unknown:
                raise ValueError(f"Mutator metadata listed unconfigured artifacts: {', '.join(unknown)}")
        actual_changes = [
            path for path in artifact_paths if before_hashes[path] != file_hash(workspace / path)
        ]
        return MutationResult(
            artifacts=actual_changes,
            hypothesis=str(
                metadata.get("hypothesis")
                or f"Command variant {experiment_index + 1} tests whether the generated artifact changes improve {self.cfg.metric.name} while passing gates."
            ),
            change_summary=self._change_summary(metadata),
        )

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
            return [artifact.path] if changed else []

        raise NotImplementedError(
            f"Mutator provider {self.cfg.mutator.provider!r} is not implemented in V0 starter."
        )

    def _stub_hypothesis(self, experiment_index: int) -> str:
        count = experiment_index % len(STUB_IMPROVEMENTS) + 1
        return (
            f"Variant {experiment_index + 1} tests whether adding {count} explicit agent behavior "
            f"rule(s) improves {self.cfg.metric.name} without breaking gates."
        )

    def _read_metadata(self, metadata_path: Path) -> dict:
        if not metadata_path.exists():
            return {}
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Mutator metadata is invalid JSON: {metadata_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"Mutator metadata must be a JSON object: {metadata_path}")
        return raw

    def _change_summary(self, metadata: dict) -> str:
        changes = metadata.get("changes") or metadata.get("change_summary")
        if isinstance(changes, list):
            rendered = "; ".join(str(change) for change in changes if str(change).strip())
            if rendered:
                return rendered
        if isinstance(changes, str) and changes.strip():
            return changes.strip()
        return "Command mutator changed the configured artifact set."
