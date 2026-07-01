# Prompt for Codex

You are building the first working version of **Looper**, an open-source CLI for self-improving loops over agent artifacts.

## Product definition

Looper lets a developer define:

1. editable artifacts
2. a command that runs the system
3. a JSON result file with a score
4. gates that must pass
5. a search loop that generates variants, evaluates them, and keeps the best passing variant

The core abstraction is:

```text
artifact + mutator + runner + evaluator + gates + selector = improvement loop
```

## Build goal

Implement a minimal but functional V0 that can be run locally on the included example.

The user should be able to run:

```bash
pip install -e .
looper init --example prompt
looper baseline
looper run --rounds 1 --variants 3
looper report
looper accept best
```

and see:

- baseline score
- variant scores
- gate pass/fail status
- winning variant
- markdown report
- ability to apply the winning artifact diff

## Non-goals for V0

Do not build:

- hosted service
- dashboard
- remote sandboxes
- full LangGraph adapter
- full CrewAI adapter
- complex MCTS
- parallel distributed execution
- auth
- telemetry
- database beyond local JSON/SQLite if necessary

## Required CLI

Use `typer`.

### `looper init`

Creates:

```text
.looper/
  state.json
  experiments/
  reports/
looper.yaml
```

If `--example prompt` is passed, copy the example config into the root.

### `looper baseline`

Runs the configured runner on the current repo/artifacts and stores baseline result under:

```text
.looper/experiments/baseline/result.json
```

### `looper run`

Arguments:

```bash
looper run --rounds 1 --variants 3
```

For each variant:

1. create a git worktree or safe copied workspace
2. mutate the configured artifact
3. run the runner command
4. run all gates
5. store result
6. update `.looper/state.json`

For V0, if git worktrees are too complex, implement a copy-based workspace runner first, but keep the abstraction named `WorkspaceBackend`.

### `looper report`

Generates:

```text
.looper/reports/latest.md
```

The report must include:

- baseline score
- all variants
- gate status
- winning variant
- changed artifact paths
- next recommended action

### `looper accept best`

Applies the winning artifact files from the winning workspace into the main working directory.

## Config schema

Implement this schema in `looper/core/config.py` using Pydantic.

```yaml
name: string

artifacts:
  - id: string
    type: prompt | markdown | yaml | json | code | generic
    path: string

runner:
  command: string
  result_path: string

metric:
  name: string
  direction: maximize | minimize

gates:
  - name: string
    command: string

search:
  variants_per_round: int
  rounds: int
  selector: best_score_with_gates

mutator:
  provider: stub | openai | anthropic | command
  command: optional string
```

For V0, implement `stub` mutator and optionally `command` mutator.

The `stub` mutator should make deterministic but visible edits to text artifacts so the example can run without API keys.

## Runner behavior

The runner executes shell commands from the workspace root.

The runner must:

- set `LOOPER_RESULT_PATH` env var to the configured result path
- set `LOOPER_ARTIFACTS` env var to JSON list of artifact paths
- capture stdout/stderr
- fail cleanly if result JSON is missing or invalid

## Gate behavior

Each gate is a shell command.

Pass if exit code is 0.
Fail if exit code is non-zero.

Store gate results per experiment.

## Experiment state

Store state in `.looper/state.json`.

Suggested structure:

```json
{
  "baseline": {
    "id": "baseline",
    "score": 0.62,
    "metrics": {},
    "status": "passed"
  },
  "experiments": [
    {
      "id": "exp_0001",
      "parent": "baseline",
      "score": 0.78,
      "metrics": {},
      "gates": [{"name": "schema", "passed": true}],
      "status": "passed",
      "workspace": ".looper/workspaces/exp_0001",
      "artifacts": ["prompts/support_agent.md"]
    }
  ],
  "best_experiment_id": "exp_0001"
}
```

## Selection logic

`best_score_with_gates`:

- ignore experiments with failed gates
- if direction is maximize, choose highest score
- if direction is minimize, choose lowest score
- compare against baseline
- mark whether improvement occurred

## Example to include

Use `examples/prompt_optimization`.

The example should have:

```text
examples/prompt_optimization/
  prompts/support_agent.md
  evals/run_eval.py
  evals/gate_no_forbidden.py
  looper.yaml
```

The eval should read the prompt and score it based on simple checks so the demo is deterministic.

For example, score higher if the prompt contains:

- "cite the policy"
- "ask a clarifying question"
- "do not invent"
- "escalate when unsure"

The stub mutator can add one of these phrases to each variant.

## Code quality

- Use clean Python 3.11+
- Keep functions small
- Add type hints
- Add helpful error messages
- Add tests for config loading, selection logic, and runner result parsing
- Avoid unnecessary dependencies
- Do not over-engineer

## README update

After implementation, update README with a real quickstart and the actual commands.

## Acceptance criteria

The project is complete when:

```bash
pip install -e .
looper init --example prompt
looper baseline
looper run --rounds 1 --variants 3
looper report
looper accept best
```

works end to end on a fresh clone.
