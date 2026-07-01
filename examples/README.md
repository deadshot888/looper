# Looper Examples

These examples are deterministic and run without API keys.

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
