from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field


ArtifactType = Literal["prompt", "markdown", "yaml", "json", "code", "generic"]
Direction = Literal["maximize", "minimize"]
SelectorType = Literal["best_score_with_gates"]
MutatorProvider = Literal["stub", "command", "openai", "anthropic"]


class ArtifactConfig(BaseModel):
    id: str
    type: ArtifactType = "generic"
    path: str


class RunnerConfig(BaseModel):
    command: str
    result_path: str = ".looper/result.json"


class MetricConfig(BaseModel):
    name: str = "score"
    direction: Direction = "maximize"


class GateConfig(BaseModel):
    name: str
    command: str


class SearchConfig(BaseModel):
    variants_per_round: int = 3
    rounds: int = 1
    selector: SelectorType = "best_score_with_gates"


class MutatorConfig(BaseModel):
    provider: MutatorProvider = "stub"
    command: Optional[str] = None


class LooperConfig(BaseModel):
    name: str = "looper-project"
    artifacts: list[ArtifactConfig]
    runner: RunnerConfig
    metric: MetricConfig = Field(default_factory=MetricConfig)
    gates: list[GateConfig] = Field(default_factory=list)
    search: SearchConfig = Field(default_factory=SearchConfig)
    mutator: MutatorConfig = Field(default_factory=MutatorConfig)

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
metric:
  name: score
  direction: maximize
gates: []
search:
  variants_per_round: 3
  rounds: 1
  selector: best_score_with_gates
mutator:
  provider: stub
"""


def load_config(path: Path) -> LooperConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return LooperConfig.model_validate(data)
