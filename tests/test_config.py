from pathlib import Path

from looper.core.config import load_config


def test_load_example_config():
    cfg = load_config(Path("examples/prompt_optimization/looper.yaml"))
    assert cfg.name == "improve-support-agent-prompt"
    assert cfg.artifacts[0].type == "prompt"
    assert cfg.metric.direction == "maximize"
