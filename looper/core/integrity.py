from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from looper.core.config import LooperConfig


def config_hash(cfg: LooperConfig) -> str:
    data = cfg.model_dump(mode="json")
    # These values control how much work one invocation schedules, not how a
    # candidate is generated, evaluated, gated, or selected.
    data["search"].pop("rounds", None)
    data["search"].pop("variants_per_round", None)
    data.pop("budget", None)
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def artifact_hashes(root: Path, artifact_paths: list[str]) -> dict[str, str]:
    return {path: file_hash(root / path) for path in artifact_paths}


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    if not path.is_file():
        return "not-a-file"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def changed_artifacts(before_root: Path, after_root: Path, artifact_paths: list[str]) -> list[str]:
    return [path for path in artifact_paths if file_hash(before_root / path) != file_hash(after_root / path)]


def project_fingerprint(root: Path, artifact_paths: list[str], cfg_hash: str) -> tuple[str, str, bool]:
    """Return a stable project hash, Git commit, and dirty flag.

    Git repositories include tracked diffs and untracked file content. Non-Git
    projects fall back to the configured artifacts plus the config hash.
    Generated .looper state is excluded by Git's normal ignore rules.
    """

    commit = _git(root, ["rev-parse", "HEAD"]).strip()
    if not commit:
        payload = json.dumps(
            {"config": cfg_hash, "artifacts": artifact_hashes(root, artifact_paths)},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest(), "", False

    digest = hashlib.sha256()
    digest.update(cfg_hash.encode("utf-8"))
    digest.update(commit.encode("utf-8"))
    digest.update(json.dumps(artifact_hashes(root, artifact_paths), sort_keys=True).encode("utf-8"))
    for args in (["diff", "--binary", "HEAD"], ["diff", "--cached", "--binary", "HEAD"]):
        digest.update(_git_bytes(root, args))

    untracked = _git_bytes(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    for raw_path in sorted(path for path in untracked.split(b"\0") if path):
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        if relative == ".looper" or relative.startswith(".looper/"):
            continue
        digest.update(raw_path)
        digest.update(file_hash(root / relative).encode("ascii"))

    dirty = bool(_git(root, ["status", "--porcelain", "--untracked-files=normal"]).strip())
    return digest.hexdigest(), commit, dirty


def _git(root: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return completed.stdout if completed.returncode == 0 else ""


def _git_bytes(root: Path, args: list[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=False,
        )
    except OSError:
        return b""
    return completed.stdout if completed.returncode == 0 else b""
