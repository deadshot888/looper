# Looper Examples

These examples are deterministic and run without API keys.

Every example supports `looper doctor`, iterative rounds, `looper diff`, and `looper accept best --dry-run` before application.

## Prompt Optimization

```bash
looper init --example prompt
looper baseline
looper run --rounds 1 --variants 3
looper report
looper accept best
```

Optimizes `examples/prompt_optimization/prompts/support_agent.md` with the built-in stub mutator.

## Agent Instructions

```bash
looper init --example instructions
looper baseline
looper run --rounds 1 --variants 3
looper report
looper accept best
```

Optimizes `examples/agent_instructions/instructions/AGENTS.md` with the built-in stub mutator.

## Tool Schema

```bash
looper init --example schema
looper baseline
looper run --rounds 1 --variants 3
looper report
looper accept best
```

Optimizes `examples/tool_schema/schemas/lookup_customer.json` with a command mutator.

## MCP Tool Selection

```bash
looper init --example mcp
looper baseline
looper run --rounds 1 --variants 3
looper report
looper accept best
```

Optimizes `examples/mcp_tool_selection/server/tools.json` for MCP tool-selection clarity, parameter descriptions, and write-action confirmation.

## Looper Dogfood

```bash
looper init --example dogfood
looper doctor
looper run --rounds 1 --variants 3
looper accept best --dry-run
looper accept best
```

Inside this repository, use the reusable configuration directly:

```bash
looper baseline --config examples/repo_dogfood/looper.yaml
looper run --rounds 1 --variants 3 --config examples/repo_dogfood/looper.yaml
looper report --config examples/repo_dogfood/looper.yaml
looper accept best --config examples/repo_dogfood/looper.yaml
```

Optimizes this repository's root `README.md` with Looper itself.
