from __future__ import annotations

from pathlib import Path, PurePath
from typing import Annotated, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    StringConstraints,
    model_validator,
)

ArtifactType = Literal["prompt", "markdown", "yaml", "json", "code", "generic"]
Direction = Literal["maximize", "minimize"]
SelectorType = Literal["best_score_with_gates"]
MutatorProvider = Literal["stub", "command"]
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactConfig(StrictModel):
    id: NonEmptyStr
    type: ArtifactType = "generic"
    path: NonEmptyStr


class RunnerConfig(StrictModel):
    command: NonEmptyStr
    result_path: NonEmptyStr = ".looper/result.json"
    timeout_seconds: PositiveFloat = 300.0
    max_output_chars: PositiveInt = 200_000
    repeats: PositiveInt = 1


class MetricConfig(StrictModel):
    name: NonEmptyStr = "score"
    direction: Direction = "maximize"


class GateConfig(StrictModel):
    name: NonEmptyStr
    command: NonEmptyStr
    timeout_seconds: PositiveFloat = 300.0
    max_output_chars: PositiveInt = 200_000


class SearchConfig(StrictModel):
    variants_per_round: PositiveInt = 3
    rounds: PositiveInt = 1
    selector: SelectorType = "best_score_with_gates"
    min_improvement: float = Field(default=0.0, ge=0.0)
    seed: int = 0


class MutatorConfig(StrictModel):
    provider: MutatorProvider = "stub"
    command: NonEmptyStr | None = None
    timeout_seconds: PositiveFloat = 300.0
    max_output_chars: PositiveInt = 200_000

    @model_validator(mode="after")
    def command_required_for_command_provider(self) -> MutatorConfig:
        if self.provider == "command" and not self.command:
            raise ValueError("mutator.command is required when mutator.provider is 'command'")
        return self


class ExecutionConfig(StrictModel):
    inherit_env: bool = False
    env_allowlist: list[NonEmptyStr] = Field(default_factory=list)


class WorkspaceConfig(StrictModel):
    include_untracked: bool = False
    exclude: list[NonEmptyStr] = Field(default_factory=list)
    max_copy_mb: PositiveFloat = 512.0


class BudgetConfig(StrictModel):
    max_experiments: PositiveInt | None = None
    max_total_cost_usd: PositiveFloat | None = None
    max_total_duration_seconds: PositiveFloat | None = None


class LooperConfig(StrictModel):
    name: NonEmptyStr = "looper-project"
    artifacts: list[ArtifactConfig] = Field(min_length=1)
    runner: RunnerConfig
    metric: MetricConfig = Field(default_factory=MetricConfig)
    gates: list[GateConfig] = Field(default_factory=list)
    search: SearchConfig = Field(default_factory=SearchConfig)
    mutator: MutatorConfig = Field(default_factory=MutatorConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)

    @model_validator(mode="after")
    def unique_names_and_paths(self) -> LooperConfig:
        _require_unique([artifact.id for artifact in self.artifacts], "artifact ids")
        _require_unique([artifact.path for artifact in self.artifacts], "artifact paths")
        _require_unique([gate.name for gate in self.gates], "gate names")
        return self

    @staticmethod
    def example_yaml() -> str:
        return """name: looper-project
artifacts:
  - id: main_prompt
    type: prompt
    path: prompts/agent.md
runner:
  command: "python evals/run_eval.py"
  result_path: ".looper/result.json"
  timeout_seconds: 300
  repeats: 1
metric:
  name: score
  direction: maximize
gates: []
search:
  variants_per_round: 3
  rounds: 1
  min_improvement: 0.0
  seed: 0
mutator:
  provider: stub
execution:
  inherit_env: false
workspace:
  include_untracked: false
  max_copy_mb: 512
budget: {}
"""


def load_config(path: Path) -> LooperConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        raise ValueError(f"Config file is empty: {path}")
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a YAML object: {path}")
    return LooperConfig.model_validate(data)


def validate_project_paths(cfg: LooperConfig, root: Path) -> None:
    root = root.resolve()
    for artifact in cfg.artifacts:
        _validate_relative_path(artifact.path, root, f"artifact {artifact.id!r}")
        relative = PurePath(artifact.path)
        if relative.parts and relative.parts[0] == ".looper":
            raise ValueError(f"Artifact paths cannot be inside .looper/: {artifact.path}")
        artifact_name = Path(artifact.path).name
        if artifact_name.startswith(".env") or Path(artifact.path).suffix.lower() in {".pem", ".key"}:
            raise ValueError(f"Secret-bearing files cannot be configured as artifacts: {artifact.path}")

    result = _validate_relative_path(cfg.runner.result_path, root, "runner.result_path")
    looper_dir = (root / ".looper").resolve()
    if not result.is_relative_to(looper_dir):
        raise ValueError("runner.result_path must resolve inside .looper/")


def _validate_relative_path(value: str, root: Path, label: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"{label} must be a relative path: {value}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"{label} escapes the project root: {value}")
    return resolved


def _require_unique(values: list[str], label: str) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValueError(f"Duplicate {label}: {', '.join(duplicates)}")
