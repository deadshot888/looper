# Looper

**Run inspectable improvement loops for agent artifacts.**

Looper is a local experiment runner for prompts, tool schemas, agent instructions, workflow configuration, and code. It generates candidates, evaluates them repeatedly, applies hard gates, advances later rounds from the current winner, and keeps every decision reviewable before acceptance.

```text
baseline snapshot
  -> generate candidate variants
  -> evaluate + apply gates
  -> verify candidate integrity
  -> advance the round winner
  -> report + inspect diff
  -> dry-run acceptance
  -> apply with conflict checks + rollback backup
```

Looper is framework-agnostic. The artifact mutator, evaluator, and gates can be any trusted local commands that follow the documented contracts.

## Quickstart

```bash
pip install looper-agent
mkdir looper-demo && cd looper-demo
looper init --example prompt
looper doctor
looper baseline
looper run --rounds 2 --variants 3
looper list
looper diff exp_0001
looper accept best --dry-run
looper accept best
```

For development:

```bash
python -m pip install -e ".[dev]"
pytest
```

## Trust Model

Commands configured as mutators, runners, and gates execute local code. Looper reduces accidental damage, but it is not a security sandbox.

- Baselines and variants run in copy workspaces, never directly in the main checkout.
- Artifact and result paths must remain inside their allowed roots.
- Candidate artifact hashes are frozen before evaluation. A runner or gate that edits one causes the experiment to fail.
- State records the configuration, baseline artifact hashes, Git revision, dirty-project fingerprint, seed, runtime, costs, and durations.
- Acceptance checks that the project and candidate still match those recorded hashes.
- Multi-file acceptance is staged, backed up under `.looper/backups/`, and rolled back if application fails.
- Commands have timeouts and stored-output limits.
- Child processes inherit only essential system variables by default. Opt specific variables in with `execution.env_allowlist`.

Review every command and candidate diff before running `looper accept`.

## Configuration

```yaml
name: improve-support-agent-prompt

artifacts:
  - id: support_prompt
    type: prompt
    path: examples/prompt_optimization/prompts/support_agent.md

runner:
  command: "python examples/prompt_optimization/evals/run_eval.py"
  result_path: ".looper/result.json"
  timeout_seconds: 300
  max_output_chars: 200000
  repeats: 3

metric:
  name: score
  direction: maximize

gates:
  - name: no_forbidden_phrase
    command: "python examples/prompt_optimization/evals/gate_no_forbidden.py"
    timeout_seconds: 60

search:
  variants_per_round: 3
  rounds: 2
  selector: best_score_with_gates
  min_improvement: 0.01
  seed: 42

mutator:
  provider: stub

execution:
  inherit_env: false
  env_allowlist:
    - MY_EVAL_API_KEY

workspace:
  include_untracked: false
  exclude:
    - data/raw/**
  max_copy_mb: 512

budget:
  max_experiments: 12
  max_total_cost_usd: 5.0
  max_total_duration_seconds: 1800
```

`rounds` are iterative: every variant in round one starts from the baseline; if that round has an improvement, every variant in round two starts from its winner. A later round only advances when it clears `min_improvement` and all gates.

## Result Contract

The runner writes JSON to `LOOPER_RESULT_PATH`. Scores must be finite numbers.

```json
{
  "score": 0.82,
  "metrics": {
    "accuracy": 0.82,
    "cost_usd": 0.04,
    "latency_seconds": 6.2
  },
  "notes": "Optional human-readable summary."
}
```

When `runner.repeats` is above one, Looper runs the evaluator repeatedly with `LOOPER_EVALUATION_INDEX`, stores every sample, and selects using the mean score. Numeric metrics are averaged; `cost_usd` is summed.

## Command Mutator Contract

Set `mutator.provider: command` to run a trusted local script that edits configured artifacts in its workspace. Looper provides:

- `LOOPER_ARTIFACTS`: JSON list of configured artifact paths
- `LOOPER_EXPERIMENT_ID`: version identifier
- `LOOPER_EXPERIMENT_INDEX`: zero-based experiment index
- `LOOPER_WORKSPACE`: isolated workspace path
- `LOOPER_MUTATION_META_PATH`: optional metadata JSON destination
- `LOOPER_SEED`: deterministic base seed
- `LOOPER_PYTHON` and `LOOPER_PYTHON_VERSION`: active runtime details

Metadata is optional:

```json
{
  "hypothesis": "Explicit confirmation language will reduce unsafe tool calls.",
  "changes": ["Added confirmation requirements."],
  "artifacts": ["server/tools.json"]
}
```

The artifact list is checked against configuration, but Looper independently hashes every configured artifact and treats the detected changes as authoritative.

## Review and Operations

```bash
looper validate                 # schema and path checks
looper doctor                   # workspace/runtime preflight
looper list [--json]            # active versions
looper show exp_0001 [--json]   # one version
looper diff exp_0001            # recorded patch
looper report                   # Markdown + HTML dashboard
looper accept best --dry-run    # integrity/conflict check only
looper reset                    # preview state reset
looper reset --yes              # archive state and reset
looper clean                    # preview workspace cleanup
looper clean --yes              # remove workspaces
looper clean --all --yes        # also remove reports/results and reset state
```

After acceptance, start a new baseline before running more experiments. This prevents results from different project states from being mixed.

## Local State

Looper writes ignored state under `.looper/`:

```text
.looper/
  state.json
  versions.jsonl
  acceptances.jsonl
  archive/
  backups/
  experiments/<version>/
    result.json
    gates.json
    diff.patch
    review.md
  reports/
    latest.md
    dashboard.html
  workspaces/
```

State writes are atomic and guarded by a process lock. The JSONL ledgers remain append-only across state resets.

## Included Examples

| Example | Artifact | Mutator | Initialize |
|---|---|---|---|
| Prompt optimization | prompt | deterministic stub | `looper init --example prompt` |
| Agent instructions | Markdown | deterministic stub | `looper init --example instructions` |
| Tool schema | JSON | command | `looper init --example schema` |
| MCP tool selection | JSON | command | `looper init --example mcp` |
| README dogfood | Markdown | command | `looper init --example dogfood` |

All five can run in a fresh directory. The dogfood initializer creates a safe starter `README.md` when one does not already exist.

## Python Runtime

Looper supports Python 3.11 through 3.14. It creates `.looper/bin/python` and `.looper/bin/python3` shims pointing to the interpreter running Looper. Set `LOOPER_PYTHON` to override that interpreter.

## Scope

Looper is an experiment engine, not an agent framework or a general-purpose sandbox. The current mutators are deterministic stubs and trusted local commands. Model-backed mutation providers, Git worktrees, framework adapters, and distributed execution remain future work.
