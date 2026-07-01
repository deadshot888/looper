from looper.core.config import LooperConfig
from looper.core.models import Experiment, GateResult, State
from looper.core.selector import Selector


def test_selector_picks_highest_passing_score():
    cfg = LooperConfig.model_validate({
        "name": "x",
        "artifacts": [{"id": "a", "type": "prompt", "path": "a.md"}],
        "runner": {"command": "echo ok", "result_path": ".looper/result.json"},
        "metric": {"name": "score", "direction": "maximize"}
    })
    state = State(experiments=[
        Experiment(id="exp_1", score=0.1, status="passed"),
        Experiment(id="exp_2", score=0.8, status="passed"),
        Experiment(id="exp_3", score=0.9, status="failed"),
    ])
    assert Selector(cfg).select_best(state) == "exp_2"


def test_selector_ignores_failed_gates():
    cfg = LooperConfig.model_validate({
        "name": "x",
        "artifacts": [{"id": "a", "type": "prompt", "path": "a.md"}],
        "runner": {"command": "echo ok", "result_path": ".looper/result.json"},
        "metric": {"name": "score", "direction": "maximize"}
    })
    state = State(experiments=[
        Experiment(id="exp_1", score=0.7, status="passed"),
        Experiment(
            id="exp_2",
            score=0.9,
            status="passed",
            gates=[GateResult(name="schema", passed=False, exit_code=1)],
        ),
    ])
    assert Selector(cfg).select_best(state) == "exp_1"


def test_selector_reports_improvement_over_baseline():
    cfg = LooperConfig.model_validate({
        "name": "x",
        "artifacts": [{"id": "a", "type": "prompt", "path": "a.md"}],
        "runner": {"command": "echo ok", "result_path": ".looper/result.json"},
        "metric": {"name": "score", "direction": "maximize"}
    })
    selector = Selector(cfg)
    baseline = Experiment(id="baseline", score=0.5, status="passed")
    best = Experiment(id="exp_1", score=0.7, status="passed")
    assert selector.improved_over_baseline(baseline, best) is True
