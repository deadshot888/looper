# Changelog

## 0.2.0 - 2026-07-10

- Added Python 3 command shims so `python` and `python3` commands run through the active Looper runtime.
- Added per-version hypotheses, change summaries, artifact diffs, and append-only `.looper/versions.jsonl` logging.
- Added generated review notes for every baseline and experiment version.
- Added a static HTML dashboard at `.looper/reports/dashboard.html`.
- Updated `looper run` and `looper report` to refresh review artifacts automatically.

## 0.1.0 - 2026-07-01

Initial public release.

- Local-first Looper CLI with `init`, `baseline`, `run`, `report`, and `accept`.
- Copy-based workspace backend for isolated variants.
- Deterministic stub mutator and command mutator.
- Shell runner with JSON result parsing.
- Command gates and best-score-with-gates selector.
- Markdown report generation.
- Examples for prompt optimization, agent instructions, JSON tool schemas, MCP tool selection, and Looper dogfooding itself.
