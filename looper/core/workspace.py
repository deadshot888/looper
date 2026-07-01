from __future__ import annotations

import shutil
from pathlib import Path


class WorkspaceBackend:
    """Copy-based workspace backend for V0.

    V1 should add a git-worktree implementation.
    """

    def __init__(self, root: Path):
        self.root = root
        self.workspaces_dir = root / ".looper" / "workspaces"
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

    def create(self, experiment_id: str) -> Path:
        dst = self.workspaces_dir / experiment_id
        if dst.exists():
            shutil.rmtree(dst)
        ignore = shutil.ignore_patterns(".git", ".looper", "__pycache__", ".pytest_cache", "*.pyc", ".venv", "venv")
        shutil.copytree(self.root, dst, ignore=ignore)
        (dst / ".looper").mkdir(exist_ok=True)
        return dst
