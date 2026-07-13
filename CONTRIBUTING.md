# Contributing

## Setup

```bash
python -m pip install -e ".[dev]"
python -m ruff check looper tests examples
python -m ruff format --check looper tests examples
python -m mypy looper
python -m pytest --cov
```

Use Python 3.11 or newer. Add tests for every behavior change, especially state compatibility, path containment, candidate integrity, command failure, and acceptance rollback.

## Design Rules

- Treat configured commands as trusted code, but keep their filesystem and environment access explicit.
- Never accept content that differs from the recorded candidate hashes and diff.
- Preserve append-only evidence across state resets.
- Keep new provider integrations optional; core examples must remain deterministic and offline.
- Avoid adding dependencies when a small standard-library implementation is clear and cross-platform.

## Pull Requests

Explain the user-visible behavior, the failure mode being prevented, and the verification performed. Do not commit `.looper/`, credentials, local environments, build output, or generated dashboards.
