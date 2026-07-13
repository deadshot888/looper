from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class GateResult(BaseModel):
    name: str
    passed: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False


class RunResult(BaseModel):
    score: float
    metrics: dict = Field(default_factory=dict)
    notes: str = ""
    raw: dict = Field(default_factory=dict)
    score_samples: list[float] = Field(default_factory=list)
    duration_seconds: float = 0.0
    cost_usd: float = 0.0

    @field_validator("score")
    @classmethod
    def finite_score(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("score must be finite")
        return value

    @field_validator("score_samples")
    @classmethod
    def finite_samples(cls, values: list[float]) -> list[float]:
        if any(not isfinite(value) for value in values):
            raise ValueError("score samples must be finite")
        return values


class VersionReview(BaseModel):
    summary: str = ""
    what_worked: list[str] = Field(default_factory=list)
    what_to_improve: list[str] = Field(default_factory=list)
    recommendation: str = ""


class RunSession(BaseModel):
    id: str
    created_at: str
    config_hash: str
    config_snapshot: dict = Field(default_factory=dict)
    baseline_artifact_hashes: dict[str, str] = Field(default_factory=dict)
    project_hash: str = ""
    git_commit: str = ""
    git_dirty: bool = False
    looper_version: str = ""
    seed: int = 0


class Experiment(BaseModel):
    id: str
    session_id: str = ""
    parent: str = "baseline"
    created_at: str = ""
    round_index: int | None = None
    variant_index: int | None = None
    score: float | None = None
    score_samples: list[float] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    notes: str = ""
    hypothesis: str = ""
    change_summary: str = ""
    diff_path: str = ""
    additions: int = 0
    deletions: int = 0
    gates: list[GateResult] = Field(default_factory=list)
    status: Literal["created", "passed", "failed", "error"] = "created"
    workspace: str = ""
    artifacts: list[str] = Field(default_factory=list)
    result_path: str = ""
    stdout: str = ""
    stderr: str = ""
    review: VersionReview = Field(default_factory=VersionReview)
    config_hash: str = ""
    baseline_artifact_hashes: dict[str, str] = Field(default_factory=dict)
    candidate_artifact_hashes: dict[str, str] = Field(default_factory=dict)
    project_hash: str = ""
    duration_seconds: float = 0.0
    cost_usd: float = 0.0

    @property
    def gates_passed(self) -> bool:
        return all(g.passed for g in self.gates)


class State(BaseModel):
    session: RunSession | None = None
    baseline: Experiment | None = None
    experiments: list[Experiment] = Field(default_factory=list)
    best_experiment_id: str | None = None
    improvement_found: bool = False
    stop_reason: str = ""
    accepted_experiment_id: str | None = None
    accepted_at: str = ""
    accepted_backup_path: str = ""
