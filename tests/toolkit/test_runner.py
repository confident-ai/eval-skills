"""run-evals runner, report, uploader (dry run), and the monitoring job."""

from __future__ import annotations

import datetime
import json

from conftest import read_jsonl, run_py, template, write_jsonl

ADAPTER = """
import time
calls = {}
class RateLimitError(Exception):
    pass
def run_case(case):
    i = int(case["id"][1:])
    calls[case["id"]] = calls.get(case["id"], 0) + 1
    if i == 3 and calls[case["id"]] == 1:
        raise RateLimitError("429 rate limited")
    if i == 7:
        time.sleep(3)
    if i == 11:
        raise ValueError("boom")
    return {"output": "<b>30 days</b>" if i % 4 else "45 days", "model": "demo", "usage": {"input_tokens": 10, "output_tokens": 5}}
"""

GRADERS = """
def window(case, result):
    ok = "30 days" in result["output"]
    return {"passed": ok, "reason": "ok" if ok else "wrong window"}
def flaky(case, result):
    if case["id"] == "c05":
        raise RuntimeError("judge down")
    return {"passed": True, "reason": "fine"}
GRADERS = {"window": window, "flaky": flaky}
"""


def setup(project):
    write_jsonl(project / ".eval/default/dataset/goldens.jsonl", [{"id": f"c{i:02d}", "input": f"q{i}", "tags": ["t"]} for i in range(16)])
    (project / ".eval/default/scripts").mkdir(parents=True)
    (project / ".eval/default/scripts/app_adapter.py").write_text(ADAPTER)
    (project / ".eval/default/graders").mkdir(parents=True)
    (project / ".eval/default/graders/graders.py").write_text(GRADERS)


def run(project, *args, check=True):
    return run_py(template("eval-run", "run_evals.py"), "--timeout-s", "1", *args, cwd=project, check=check)


def test_dry_run_prints_scope_only(project):
    setup(project)
    out = run(project, "--variant", "baseline", "--reps", "2", "--dry-run")
    assert "16 cases × 2 reps = 32 slots" in out.stdout
    assert not (project / ".eval/default/runs/baseline").exists()


def test_errors_are_never_scored_and_resume_is_idempotent(project):
    setup(project)
    run(project, "--variant", "baseline", "--reps", "2")
    rows = read_jsonl(project / ".eval/default/runs/baseline/results.jsonl")
    errors = read_jsonl(project / ".eval/default/runs/baseline/errors.jsonl")
    ids = {r["case_id"] for r in rows}
    assert "c03" in ids  # rate limit retried and succeeded
    assert not {"c05", "c07", "c11"} & ids  # grader error, timeout, harness error: no scored rows
    classes = {(e["stage"], e["failure_class"]) for e in errors}
    assert {("app", "timeout"), ("app", "harness"), ("app", "rate-limit"), ("grader", "harness")} <= classes
    summary = json.loads((project / ".eval/default/runs/baseline/summary.json").read_text())
    assert summary["missing_slots"] == 6 and summary["rows"] == 26
    lo, hi = summary["ci95_all"]
    assert lo <= summary["pass_rate_all"] <= hi

    run(project, "--variant", "baseline", "--reps", "2")
    again = read_jsonl(project / ".eval/default/runs/baseline/results.jsonl")
    assert len({(r["case_id"], r["rep"]) for r in again}) == len(again)


def test_paired_compare_and_report_escaping(project):
    setup(project)
    run(project, "--variant", "baseline", "--reps", "2")
    run(project, "--variant", "v1", "--reps", "2", "--compare", "baseline")
    compare = json.loads((project / ".eval/default/runs/v1/summary.json").read_text())["compare"]
    assert compare["verdict"] == "within noise" and compare["delta"] == 0

    run_py(template("eval-run", "report.py"), cwd=project)
    html = (project / ".eval/default/runs/report.html").read_text()
    assert "<b>30 days</b>" not in html and "&lt;b&gt;30 days&lt;/b&gt;" in html
    assert "<script" not in html


def test_collect_only_and_upload_dry_run(project):
    setup(project)
    out = run(project, "--variant", "collect", "--graders", "none")
    assert "Collected outputs" in out.stdout
    rows = read_jsonl(project / ".eval/default/runs/collect/results.jsonl")
    assert rows and all(r["grades"] == {} for r in rows)
    up = run_py(template("eval-run", "upload_results.py"), "--variant", "collect", "--collection", "core", "--dry-run", cwd=project)
    assert f"Would upload {len(rows)} test cases" in up.stdout


def test_monitor_alerts_on_drop(project):
    now = datetime.datetime.now(datetime.timezone.utc)
    traces = [{"trace_id": f"t{i}", "started_at": (now - datetime.timedelta(hours=1)).isoformat(),
               "input": "q", "output": "30 days" if i % 5 else "45 days", "metadata": {"environment": "production"}}
              for i in range(40)]
    write_jsonl(project / ".eval/default/traces/traces.jsonl", traces)
    (project / ".eval/default/graders").mkdir(parents=True)
    (project / ".eval/default/graders/graders.py").write_text(GRADERS.replace('    if case["id"] == "c05":\n        raise RuntimeError("judge down")\n', ""))
    m = template("eval-maintain", "monitor.py")
    first = run_py(m, "--only", "window", "--seed", "1", cwd=project)
    assert "window: 0.80" in first.stdout
    write_jsonl(project / ".eval/default/traces/traces.jsonl", [dict(t, output="45 days") for t in traces])
    second = run_py(m, "--only", "window", "--seed", "1", cwd=project, check=False)
    assert second.returncode == 2 and "below last window" in second.stdout
    assert len(read_jsonl(project / ".eval/default/monitoring/trend.jsonl")) == 2


DETERMINISTIC_ADAPTER = """
def run_case(case):
    return {"output": "30 days" if int(case["id"][1:]) % 4 else "45 days"}
"""


def test_stale_rows_block_resume(project):
    setup(project)
    (project / ".eval/default/scripts/app_adapter.py").write_text(DETERMINISTIC_ADAPTER)
    run(project, "--variant", "baseline", "--reps", "2")
    rows = read_jsonl(project / ".eval/default/runs/baseline/results.jsonl")
    assert rows and all(r["case_hash"] and r["harness_hash"] for r in rows)

    # Change one case's input but keep its id: resuming must not reuse the old output.
    cases = read_jsonl(project / ".eval/default/dataset/goldens.jsonl")
    cases[0]["input"] = "a different question"
    write_jsonl(project / ".eval/default/dataset/goldens.jsonl", cases)
    blocked = run(project, "--variant", "baseline", "--reps", "2", check=False)
    assert blocked.returncode != 0 and "different case definition" in blocked.stderr
    run(project, "--variant", "baseline", "--reps", "2", "--discard-stale")
    rows = read_jsonl(project / ".eval/default/runs/baseline/results.jsonl")
    assert [r["input"] for r in rows if r["case_id"] == "c00"] == ["a different question"] * 2
    assert len(read_jsonl(project / ".eval/default/runs/baseline/stale.jsonl")) == 2

    # Changing a grader also invalidates earlier rows.
    graders = project / ".eval/default/graders/graders.py"
    graders.write_text(graders.read_text() + "\n# tweak\n")
    assert run(project, "--variant", "baseline", "--reps", "2", check=False).returncode != 0


def test_interval_is_over_cases_not_runs(project):
    setup(project)
    (project / ".eval/default/scripts/app_adapter.py").write_text(DETERMINISTIC_ADAPTER)
    run(project, "--variant", "r1", "--reps", "1", "--only", "window")
    run(project, "--variant", "r4", "--reps", "4", "--only", "window")
    s1 = json.loads((project / ".eval/default/runs/r1/summary.json").read_text())
    s4 = json.loads((project / ".eval/default/runs/r4/summary.json").read_text())
    assert s4["rows"] == 4 * s1["rows"]
    assert s1["ci95_all"] == s4["ci95_all"] and s4["cases_scored"] == 16


def test_compare_ids_restricts_the_decision(project):
    setup(project)
    (project / ".eval/default/scripts/app_adapter.py").write_text(DETERMINISTIC_ADAPTER)
    run(project, "--variant", "baseline", "--only", "window")
    (project / ".eval/default/runs/validation_ids.json").write_text(json.dumps(["c00", "c01", "c02", "c03"]))
    run(project, "--variant", "v1", "--only", "window", "--compare", "baseline", "--compare-ids", ".eval/default/runs/validation_ids.json")
    compare = json.loads((project / ".eval/default/runs/v1/summary.json").read_text())["compare"]
    assert compare["n_cases"] == 4
