"""Production monitor: pooled reference, one-sided drop test, incomplete windows, legacy trend rows."""

from __future__ import annotations

import datetime
import importlib.util
import os
import random

from conftest import read_jsonl, run_py, template, write_jsonl

GRADERS = """
import os
def policy(case, result):
    if os.environ.get("JUDGE_DOWN"):
        raise RuntimeError("judge API 503")
    return {"passed": result["output"] == "ok"}
GRADERS = {"policy": policy}
"""


def setup(project):
    (project / ".eval/default/graders").mkdir(parents=True)
    (project / ".eval/default/graders/graders.py").write_text(GRADERS)


def window(project, passes: int, n: int = 200) -> None:
    """Write a fresh window of n traces, exactly `passes` of which pass; the default sample grades all of them."""
    started = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
    write_jsonl(project / ".eval/default/traces/traces.jsonl",
                [{"trace_id": f"t{i}", "started_at": started, "input": "q", "output": "ok" if i < passes else "bad"} for i in range(n)])


def monitor(project, *args, judge_down=False):
    env = {**os.environ, "JUDGE_DOWN": "1"} if judge_down else {k: v for k, v in os.environ.items() if k != "JUDGE_DOWN"}
    return run_py(template("eval-maintain", "monitor.py"), "--seed", "1", *args, cwd=project, env=env, check=False)


def trend(project) -> list[dict]:
    return read_jsonl(project / ".eval/default/monitoring/trend.jsonl")


def test_outage_is_incomplete_and_does_not_mask_the_next_regression(project):
    setup(project)
    window(project, 184)
    assert monitor(project).returncode == 0
    outage = monitor(project, judge_down=True)
    assert outage.returncode == 3 and "incomplete" in outage.stdout
    row = trend(project)[-1]
    assert row["status"] == "incomplete" and row["n"] == 0 and row["errors"] == 200
    assert row["pass_rate"] is None and row["ci95"] is None  # unknown, not [0, 0]

    window(project, 120)
    crash = monitor(project)
    assert crash.returncode == 2 and "regression" in crash.stdout
    row = trend(project)[-1]
    assert row["status"] == "regression" and row["reference"] == {"windows": 1, "n": 200, "pass_rate": 0.92}


def test_first_window_then_ordinary_noise_does_not_alert(project):
    setup(project)
    window(project, 184)
    assert monitor(project).returncode == 0 and trend(project)[-1]["status"] == "no-reference"
    window(project, 176)  # 92% -> 88%: within noise for n=200
    result = monitor(project)
    row = trend(project)[-1]
    assert result.returncode == 0 and row["status"] == "ok"
    assert row["delta"] == -0.04 and row["delta_upper"] > 0


def test_windows_below_a_configured_floor_are_incomplete_and_never_become_the_reference(project):
    setup(project)
    window(project, 184)
    monitor(project)
    window(project, 9, n=10)
    small = monitor(project, "--min-n", "30")
    assert small.returncode == 3 and trend(project)[-1]["status"] == "incomplete"
    window(project, 180)
    assert monitor(project, "--min-n", "30").returncode == 0
    assert trend(project)[-1]["reference"]["n"] == 200  # the 10-trace window was skipped


def test_partial_grader_errors_above_the_limit_make_a_window_incomplete(project):
    setup(project)
    (project / ".eval/default/graders/graders.py").write_text(GRADERS.replace(
        'if os.environ.get("JUDGE_DOWN"):', 'if os.environ.get("JUDGE_DOWN") or case["id"] in {f"t{i}" for i in range(0, 200, 8)}:'))
    window(project, 184)  # 25 of 200 grades error (12.5%)
    result = monitor(project)
    assert result.returncode == 3 and trend(project)[-1]["errors"] == 25
    assert monitor(project, "--max-error-rate", "0.2").returncode == 0


def test_a_small_window_that_collapses_still_alerts(project):
    setup(project)
    window(project, 184)
    monitor(project)
    window(project, 2, n=12)  # low traffic, but 2/12 against 92% is not noise
    assert monitor(project).returncode == 2 and trend(project)[-1]["status"] == "regression"


def test_bad_settings_exit_1_not_the_regression_code(project):
    setup(project)
    window(project, 184)
    assert monitor(project, "--alpha", "5").returncode == 1


def test_a_lasting_regression_keeps_alerting_instead_of_becoming_the_baseline(project):
    setup(project)
    window(project, 184)
    monitor(project)
    window(project, 120)
    assert monitor(project).returncode == 2
    window(project, 122)
    again = monitor(project)
    assert again.returncode == 2
    assert trend(project)[-1]["reference"] == {"windows": 1, "n": 200, "pass_rate": 0.92}


def test_reference_pools_recent_windows_and_min_drop_sets_the_effect_size(project):
    setup(project)
    for _ in range(3):
        window(project, 184)
        monitor(project)
    history = project / ".eval/default/monitoring/trend.jsonl"
    (project / "copy.jsonl").write_text(history.read_text())
    window(project, 160)  # 92% -> 80%: significant, but smaller than the drop we said matters
    assert monitor(project, "--min-drop", "0.15").returncode == 0
    assert trend(project)[-1]["reference"]["windows"] == 3 and trend(project)[-1]["status"] == "ok"
    assert monitor(project, "--reference-windows", "2", "--out", "copy.jsonl").returncode == 2
    assert read_jsonl(project / "copy.jsonl")[-1]["reference"] == {"windows": 2, "n": 400, "pass_rate": 0.92}


def test_trend_rows_written_before_statuses_still_serve_as_reference(project):
    setup(project)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    legacy = [
        {"window_end": now, "hours": 24, "mode": "policy", "n": 200, "pass_rate": 0.92, "ci95": [0.8747, 0.9502], "errors": 0},
        {"window_end": now, "hours": 24, "mode": "policy", "n": 0, "pass_rate": None, "ci95": [0.0, 0.0], "errors": 200},
    ]
    write_jsonl(project / ".eval/default/monitoring/trend.jsonl", legacy)
    window(project, 120)
    assert monitor(project).returncode == 2
    assert trend(project)[-1]["reference"] == {"windows": 1, "n": 200, "pass_rate": 0.92}


def _load_monitor():
    spec = importlib.util.spec_from_file_location("monitor", template("eval-maintain", "monitor.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_drop_test_false_alert_rate_and_power():
    m = _load_monitor()
    rng = random.Random(0)
    draw = lambda n, p: sum(rng.random() < p for _ in range(n))
    trials, n, ref_n = 1500, 200, 1400  # one window against a week of pooled windows

    def alert_rate(p_now):
        return sum(m.drop_test(draw(n, p_now), n, draw(ref_n, 0.92), ref_n, 0.01)[1] < 0 for _ in range(trials)) / trials

    assert alert_rate(0.92) <= 0.02  # unchanged traffic: close to alpha = 0.01
    assert alert_rate(0.82) >= 0.9  # a ten-point drop is caught


def test_drop_test_matches_newcombe_reference_values():
    m = _load_monitor()
    # Newcombe (1998), method 10, two-sided 95% (one-sided 97.5%) example: 56/70 vs 48/80 -> 0.0524 to 0.3339.
    delta, upper = m.drop_test(56, 70, 48, 80, 0.025)
    assert round(delta, 4) == 0.2 and round(upper, 4) == 0.3339
    # Swap the arms: the upper bound of the reverse difference is minus the lower bound above.
    _, upper_rev = m.drop_test(48, 80, 56, 70, 0.025)
    assert round(upper_rev, 4) == -0.0524
    assert m.wilson(0, 0) is None
