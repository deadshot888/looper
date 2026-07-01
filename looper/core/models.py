from __future__ import annotations

from pydantic import BaseModel, Field


class GateResult(BaseModel):
    name: str
    passed: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""


class RunResult(BaseModel):
    score: float
    metrics: dict = Field(default_factory=dict)
    notes: str = ""
    raw: dict = Field(default_factory=dict)


class Experiment(BaseModel):
    id: str
    parent: str = "baseline"
    score: float | None = None
    metrics: dict = Field(default_factory=dict)
    notes: str = ""
    gates: list[GateResult] = Field(default_factory=list)
    status: str = "created"
    workspace: str = ""
    artifacts: list[str] = Field(default_factory=list)
    result_path: str = ""
    stdout: str = ""
    stderr: str = ""

    @property
    def gates_passed(self) -> bool:
        return all(g.passed for g in self.gates)


class State(BaseModel):
    baseline: Experiment | None = None
    experiments: list[Experiment] = Field(default_factory=list)
    best_experiment_id: str | None = None
    improvement_found: bool = False
