# Architecture

## Execution Model

```text
CLI
  -> strict config + path validation
  -> state/session lock
  -> isolated baseline workspace
  -> iterative experiment engine
       -> parent workspace copy
       -> mutator
       -> candidate hash + diff
       -> repeated evaluator runs
       -> gates
       -> candidate hash verification
       -> selector / next-round parent
  -> report + dashboard
  -> conflict-aware acceptance + backup
```

The active session stores a canonical configuration hash, baseline artifact hashes, Git commit and project fingerprint. Experiments from incompatible project states are never mixed silently.

## Candidate Lifecycle

1. Copy the baseline or prior winning workspace.
2. Run the configured mutator.
3. Detect changed configured artifacts independently of mutator metadata.
4. Store the cumulative diff against the baseline and freeze candidate hashes.
5. Run evaluator repetitions and gates with bounded commands.
6. Re-hash artifacts. Any evaluator or gate mutation marks the version as an error.
7. Select the best passing candidate. Advance it only if it beats its parent by `min_improvement`.

The evaluator writes only beneath the workspace `.looper/` directory. Candidate artifacts are logically read-only after mutation.

## Acceptance

Acceptance verifies:

- active configuration and project fingerprints match the session;
- root artifacts still match their baseline hashes;
- candidate workspace paths remain under `.looper/workspaces/`;
- candidate artifacts still match their frozen hashes;
- every source and destination exists within its allowed root.

`--dry-run` performs all checks without writes. Real acceptance stages all files, copies originals to `.looper/backups/`, replaces destinations, and rolls back already-applied files if a later replacement fails.

## Process Boundary

Mutators, evaluators, and gates are trusted local commands, not sandboxed code. The process layer adds timeouts, process-tree termination, output truncation, and deterministic environment variables. By default children receive an essential system environment rather than every parent secret; additional variable names must be allowlisted.

## Workspace Boundary

Git projects copy tracked files by default. `workspace.include_untracked` opts nonignored untracked files in. Non-Git projects use a recursive copy. Generated state, caches, virtual environments, common secret files, and configured exclusions are omitted. `workspace.max_copy_mb` blocks unexpectedly large copies.

## State Layout

```text
.looper/
  state.json                 # atomic active-session state
  state.lock                 # short-lived process lock
  versions.jsonl             # append-only version ledger
  acceptances.jsonl          # append-only acceptance ledger
  archive/                   # state snapshots made by reset
  backups/                   # pre-acceptance artifact backups
  experiments/<id>/
    result.json
    gates.json
    stdout.txt
    stderr.txt
    diff.patch
    review.json
    review.md
  reports/
    latest.md
    dashboard.html
  workspaces/
```

## Modules

- `config.py`: strict schema and path policy.
- `workspace.py`: bounded Git-aware copies.
- `process.py`: bounded shell execution.
- `integrity.py`: configuration, project, and artifact hashes.
- `runner.py`: result validation and repeated-evaluation aggregation.
- `gates.py`: hard pass/fail constraints.
- `mutator.py`: deterministic or command-based candidate mutation.
- `engine.py`: sessions, iterative rounds, budgets, persistence, and acceptance.
- `selector.py`: direction-aware threshold selection.
- `report.py`: Markdown and dashboard generation.

## Design Constraints

- local-first and framework-neutral;
- explicit trust boundary for commands;
- inspectable and append-only decision evidence;
- immutable candidate content during evaluation;
- no silent reuse of stale baselines;
- no acceptance without a reviewable diff and verified hashes.
