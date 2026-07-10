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


class VersionReview(BaseModel):
    summary: str = ""
    what_worked: list[str] = Field(default_factory=list)
    what_to_improve: list[str] = Field(default_factory=list)
    recommendation: str = ""


class Experiment(BaseModel):
    id: str
    parent: str = "baseline"
    created_at: str = ""
    round_index: int | None = None
    variant_index: int | None = None
    score: float | None = None
    metrics: dict = Field(default_factory=dict)
    notes: str = ""
    hypothesis: str = ""
    change_summary: str = ""
    diff_path: str = ""
    additions: int = 0
    deletions: int = 0
    gates: list[GateResult] = Field(default_factory=list)
    status: str = "created"
    workspace: str = ""
    artifacts: list[str] = Field(default_factory=list)
    result_path: str = ""
    stdout: str = ""
    stderr: str = ""
    review: VersionReview = Field(default_factory=VersionReview)

    @property
    def gates_passed(self) -> bool:
        return all(g.passed for g in self.gates)


class State(BaseModel):
    baseline: Experiment | None = None
    experiments: list[Experiment] = Field(default_factory=list)
    best_experiment_id: str | None = None
    improvement_found: bool = False
