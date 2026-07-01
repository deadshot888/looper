# Looper

**Set up self-improving loops for your agents.**

Looper is an open-source experiment runner for agentic systems. Give it an editable artifact, an eval command, and gates. It generates variants, runs the evals, discards unsafe changes, and keeps what improves.

> Working tagline. We can refine later.

## What Looper Does

Looper turns this:

```text
prompt / tool schema / RAG config / workflow / code
```

into this:

```text
baseline
  -> generate variants
  -> run evals
  -> apply gates
  -> select winner
  -> produce diff + report
  -> accept/reject
```

The initial version is framework-agnostic. It does not care whether the underlying agent is LangGraph, CrewAI, OpenAI Agents SDK, Claude Code, custom Python, or a shell script. As long as the system can be run through a command and produce a metric, Looper can optimize it.

## Why This Exists

Agent systems are still hand-tuned: prompts, tool descriptions, workflow configs, model choices, RAG parameters, and evals are manually edited until they "feel better."

Looper makes that process experimental:

- define what artifact can change
- define how to run the system
- define how to score it
- define what must never regress
- let agents try variants
- keep only passing improvements

## V0 Scope

V0 supports:

- one or more editable artifacts
- local copy-based workspace isolation
- shell-based runner
- JSON result contract
- command-based gates
- stub and command mutators
- best-score selector
- markdown report
- accept winning diff

## Quickstart

From a fresh clone:

```bash
pip install -e .

looper init --example prompt
looper baseline
looper run --rounds 1 --variants 3
looper report
looper accept best
```

This writes local state under `.looper/`, including:

- `.looper/experiments/baseline/result.json`
- `.looper/experiments/exp_0001/result.json`
- `.looper/reports/latest.md`
- `.looper/workspaces/exp_0001/`

The prompt example is deterministic. The stub mutator appends visible support-agent guidance, the eval scores the prompt, the gate checks for forbidden phrases, and `looper accept best` copies the winning prompt back into the working tree.

## Included Examples

Looper ships with four deterministic examples:

| Example | Artifact type | Mutator | Start command |
|---|---|---|---|
| Prompt optimization | `prompt` | `stub` | `looper init --example prompt` |
| Agent instructions | `markdown` | `stub` | `looper init --example instructions` |
| Tool schema | `json` | `command` | `looper init --example schema` |
| MCP tool selection | `json` | `command` | `looper init --example mcp` |

Each example uses the same workflow:

```bash
looper baseline
looper run --rounds 1 --variants 3
looper report
looper accept best
```

## Example `looper.yaml`

```yaml
name: improve-support-agent-prompt

artifacts:
  - id: support_prompt
    type: prompt
    path: examples/prompt_optimization/prompts/support_agent.md

runner:
  command: "python examples/prompt_optimization/evals/run_eval.py"
  result_path: ".looper/result.json"

metric:
  name: score
  direction: maximize

gates:
  - name: no_forbidden_phrase
    command: "python examples/prompt_optimization/evals/gate_no_forbidden.py"

search:
  variants_per_round: 3
  rounds: 1
  selector: best_score_with_gates

mutator:
  provider: stub
```

## Result Contract

The runner command must write JSON to the configured `result_path`.

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

## Command Mutator Contract

Set `mutator.provider: command` when you want a local script to edit artifacts. Looper runs the command from the workspace root and provides:

- `LOOPER_ARTIFACTS`: JSON list of configured artifact paths
- `LOOPER_EXPERIMENT_INDEX`: zero-based variant index
- `LOOPER_WORKSPACE`: path to the isolated workspace

The command should edit the configured artifact files in place and exit with code `0`.

## What Looper Is Not

- not another agent framework
- not another observability dashboard
- not only a prompt optimizer
- not only a code optimizer
- not tied to CrewAI, LangGraph, or Claude Code

## What Looper Should Become

Looper should become the local-first engine for self-improving agent systems:

```text
editable artifact + evaluator + gates = improvement loop
```

Initial artifact types:

- prompts
- MCP/tool schemas
- RAG configs
- workflow YAML/JSON
- markdown instructions
- code files

Later adapters:

- LangGraph
- CrewAI
- OpenAI Agents SDK
- Claude Code plugin
- Cursor / Codex plugin
- MCP server/tool-schema optimization
