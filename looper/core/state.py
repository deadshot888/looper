from __future__ import annotations

import json
import os
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from looper.core.errors import LooperError
from looper.core.models import State


class StateStore:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / ".looper" / "state.json"
        self.lock_path = root / ".looper" / "state.lock"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> State:
        if not self.path.exists():
            return State()
        try:
            return State.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            raise LooperError(
                f"Looper state is corrupt or incompatible: {self.path}. "
                "Run 'looper reset --yes' to archive it and start a new session."
            ) from exc

    def save(self, state: State) -> None:
        temp_path = self.path.with_suffix(".json.tmp")
        temp_path.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
        os.replace(temp_path, self.path)

    def reset(self, archive: bool = True) -> Path | None:
        archived: Path | None = None
        if archive and self.path.exists():
            archive_dir = self.root / ".looper" / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            archived = archive_dir / f"{timestamp}-state.json"
            shutil.copy2(self.path, archived)
        self.save(State())
        return archived

    @contextmanager
    def lock(self, timeout_seconds: float = 1.0) -> Iterator[None]:
        deadline = time.monotonic() + timeout_seconds
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(descriptor, str(os.getpid()).encode("ascii"))
            except FileExistsError:
                if time.monotonic() >= deadline:
                    owner = self.lock_path.read_text(encoding="utf-8", errors="replace").strip()
                    raise LooperError(
                        f"Another Looper process is using this project (pid {owner or 'unknown'})."
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            if descriptor is not None:
                os.close(descriptor)
            self.lock_path.unlink(missing_ok=True)
