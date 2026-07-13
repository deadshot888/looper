from __future__ import annotations


class LooperError(RuntimeError):
    """Base class for expected, user-facing Looper failures."""


class StateConflictError(LooperError):
    """Raised when saved experiment state no longer matches the project."""


class CommandTimeoutError(LooperError):
    """Raised when a configured command exceeds its timeout."""


class ArtifactIntegrityError(LooperError):
    """Raised when evaluation changes an immutable candidate artifact."""
