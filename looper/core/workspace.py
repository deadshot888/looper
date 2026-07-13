from __future__ import annotations

import fnmatch
import shutil
import subprocess
from pathlib import Path

from looper.core.config import WorkspaceConfig
from looper.core.errors import LooperError

ALWAYS_EXCLUDED = (
    ".git",
    ".looper",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    "*.pyc",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "credentials.json",
)


class WorkspaceBackend:
    """Creates bounded copy workspaces while respecting Git ignore rules."""

    def __init__(
        self,
        root: Path,
        cfg: WorkspaceConfig | None = None,
        required_paths: list[str] | None = None,
    ):
        self.root = root.resolve()
        self.cfg = cfg or WorkspaceConfig()
        self.required_paths = required_paths or []
        self.workspaces_dir = self.root / ".looper" / "workspaces"
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

    def create(self, experiment_id: str, source: Path | None = None) -> Path:
        source = (source or self.root).resolve()
        dst = (self.workspaces_dir / experiment_id).resolve()
        if not dst.is_relative_to(self.workspaces_dir.resolve()):
            raise LooperError(f"Invalid experiment id: {experiment_id}")
        if dst.exists():
            shutil.rmtree(dst)

        files = self._source_files(source)
        total_bytes = sum(path.stat().st_size for path in files if path.is_file())
        max_bytes = float(self.cfg.max_copy_mb) * 1024 * 1024
        if total_bytes > max_bytes:
            raise LooperError(
                f"Workspace copy would be {total_bytes / 1024 / 1024:.1f} MiB, "
                f"above workspace.max_copy_mb={self.cfg.max_copy_mb:g}."
            )

        dst.mkdir(parents=True, exist_ok=True)
        for source_path in files:
            relative = source_path.relative_to(source)
            target = dst / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source_path.is_symlink():
                target.symlink_to(source_path.readlink(), target_is_directory=source_path.is_dir())
            else:
                shutil.copy2(source_path, target)
        (dst / ".looper").mkdir(exist_ok=True)
        return dst

    def estimate(self, source: Path | None = None) -> tuple[int, int]:
        files = self._source_files((source or self.root).resolve())
        return len(files), sum(path.stat().st_size for path in files if path.is_file())

    def _source_files(self, source: Path) -> list[Path]:
        git_files = self._git_files(source) if source == self.root else None
        candidates = (
            git_files if git_files is not None else [path for path in source.rglob("*") if path.is_file()]
        )
        if source == self.root and git_files is not None:
            candidates.extend(
                path
                for relative in self.required_paths
                if (path := source / relative).is_file() and path not in candidates
            )
        return sorted(
            (path for path in candidates if path.is_file() and not self._excluded(path.relative_to(source))),
            key=lambda path: path.as_posix(),
        )

    def _git_files(self, source: Path) -> list[Path] | None:
        args = ["git", "-C", str(source), "ls-files", "--cached", "-z", "--", "."]
        if self.cfg.include_untracked:
            args = [
                "git",
                "-C",
                str(source),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                ".",
            ]
        try:
            completed = subprocess.run(args, capture_output=True, check=False)
            prefix_result = subprocess.run(
                ["git", "-C", str(source), "rev-parse", "--show-prefix"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if completed.returncode != 0 or prefix_result.returncode != 0:
            return None

        prefix = prefix_result.stdout.strip().replace("\\", "/")
        paths: list[Path] = []
        for raw in completed.stdout.split(b"\0"):
            if not raw:
                continue
            relative = raw.decode("utf-8", errors="surrogateescape").replace("\\", "/")
            if prefix and relative.startswith(prefix):
                relative = relative[len(prefix) :]
            candidate = (source / relative).resolve()
            if candidate.is_relative_to(source) and candidate.exists():
                paths.append(candidate)
        return paths

    def _excluded(self, relative: Path) -> bool:
        normalized = relative.as_posix()
        parts = relative.parts
        patterns = (*ALWAYS_EXCLUDED, *self.cfg.exclude)
        for pattern in patterns:
            clean = pattern.rstrip("/")
            if clean in parts or fnmatch.fnmatch(relative.name, clean) or fnmatch.fnmatch(normalized, clean):
                return True
        return False
