from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiffSummary:
    patch: str
    additions: int
    deletions: int


def build_artifact_diff(root: Path, workspace: Path, artifact_paths: list[str]) -> DiffSummary:
    patches: list[str] = []
    additions = 0
    deletions = 0

    for artifact_path in artifact_paths:
        before_path = root / artifact_path
        after_path = workspace / artifact_path
        before = _read_lines(before_path)
        after = _read_lines(after_path)
        diff_lines = list(
            difflib.unified_diff(
                before,
                after,
                fromfile=f"a/{artifact_path}",
                tofile=f"b/{artifact_path}",
                lineterm="",
            )
        )
        if not diff_lines:
            continue
        patches.extend(diff_lines)
        patches.append("")
        for line in diff_lines:
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                additions += 1
            elif line.startswith("-"):
                deletions += 1

    patch = "\n".join(patches).rstrip()
    if patch:
        patch += "\n"
    return DiffSummary(patch=patch, additions=additions, deletions=deletions)


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()
