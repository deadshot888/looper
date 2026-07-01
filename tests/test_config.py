from pathlib import Path

from looper.core.config import load_config


def test_load_example_config():
    cfg = load_config(Path("examples/prompt_optimization/looper.yaml"))
    assert cfg.name == "improve-support-agent-prompt"
    assert cfg.artifacts[0].type == "prompt"
    assert cfg.metric.direction == "maximize"


def test_load_all_example_configs():
    paths = [
        Path("examples/prompt_optimization/looper.yaml"),
        Path("examples/agent_instructions/looper.yaml"),
        Path("examples/tool_schema/looper.yaml"),
        Path("examples/mcp_tool_selection/looper.yaml"),
    ]

    configs = [load_config(path) for path in paths]

    assert [config.name for config in configs] == [
        "improve-support-agent-prompt",
        "improve-agent-instructions",
        "improve-tool-schema",
        "improve-mcp-tool-selection",
    ]
    assert configs[1].artifacts[0].type == "markdown"
    assert configs[2].artifacts[0].type == "json"
    assert configs[2].mutator.provider == "command"
    assert configs[3].artifacts[0].type == "json"
    assert configs[3].mutator.provider == "command"
