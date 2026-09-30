"""error-analysis sampler, validate-graders validate.py, improve-app split_cases.py."""

from __future__ import annotations

import json

from conftest import run_py, template, write_jsonl

GRADERS = """
def invented_policy(case, result):
    ok = "30 days" in str(result["output"])
    return {"passed": ok, "reason": "matches" if ok else "differs"}

def broken(case, result):
    raise RuntimeError("judge API down")

GRADERS = {"invented-policy": invented_policy, "broken": broken}
"""


def make_labeled_project(project, n=60):
    traces, annotations = [], {}
    for i in range(n):
        bad = i % 3 == 0
        traces.append({"trace_id": f"t{i:03d}", "input": "window?", "output": "45 days" if bad else "30 days",
                       "duration_ms": 100 + i, "steps": [{"type": "retriever", "output": ["30 days"]}]})
        human = "fail" if bad or i in (4, 8) else "pass"
        annotations[f"t{i:03d}"] = {"verdict": None, "note": "", "labels": {"invented-policy": human, "broken": human}}
    write_jsonl(project / ".eval/default/traces/traces.jsonl", traces)
    (project / ".eval/default/review-app").mkdir(parents=True)
    (project / ".eval/default/review-app/annotations.json").write_text(json.dumps(annotations))
    (project / ".eval/default/graders").mkdir(parents=True)
    (project / ".eval/default/graders/graders.py").write_text(GRADERS)


def test_sampler_appends_without_duplicates(project):
    write_jsonl(project / ".eval/default/traces/traces.jsonl",
                [{"trace_id": f"x{i}", "input": "q" * i, "output": "a", "duration_ms": i * 10,
                  "steps": [{"type": "tool"}] * (i % 4), "error": "Timeout" if i == 5 else None} for i in range(50)])
    sampler = template("eval-discover", "sample_traces.py")
    run_py(sampler, "--n", "15", cwd=project)
    run_py(sampler, "--n", "15", cwd=project)
    sample = json.loads((project / ".eval/default/review-app/samples.json").read_text())
    assert len(sample) == 30 and len(set(sample)) == 30
    assert "x5" in sample[:15]  # errored traces are picked first


def test_sampler_skips_annotated(project):
    write_jsonl(project / ".eval/default/traces/traces.jsonl", [{"trace_id": f"x{i}", "input": "q", "output": "a"} for i in range(10)])
    (project / ".eval/default/review-app").mkdir(parents=True)
    (project / ".eval/default/review-app/annotations.json").write_text(json.dumps({f"x{i}": {} for i in range(8)}))
    run_py(template("eval-discover", "sample_traces.py"), "--n", "10", cwd=project)
    assert sorted(json.loads((project / ".eval/default/review-app/samples.json").read_text())) == ["x8", "x9"]


def test_validate_split_run_and_test_once(project):
    make_labeled_project(project)
    v = template("eval-grade", "validate.py")
    out = run_py(v, "split", "--mode", "invented-policy", cwd=project)
    assert "development:" in out.stdout
    again = run_py(v, "split", "--mode", "invented-policy", cwd=project, check=False)
    assert again.returncode != 0 and "already exist" in again.stderr

    run_py(v, "run", "--mode", "invented-policy", "--split", "validation", cwd=project)
    report = json.loads((project / ".eval/default/validation/invented-policy-validation.json").read_text())
    assert report["tpr"] == 1.0 and report["tnr"] < 1.0
    assert all(d["kind"].startswith("false pass") for d in report["disagreements"])

    run_py(v, "run", "--mode", "invented-policy", "--split", "test", cwd=project)
    second = run_py(v, "run", "--mode", "invented-policy", "--split", "test", cwd=project, check=False)
    assert second.returncode != 0 and "already measured once" in second.stderr

    corrected = run_py(v, "correct", "--mode", "invented-policy", "--observed-pass-rate", "0.7", cwd=project)
    assert "corrected" in corrected.stdout


def test_validate_counts_grader_errors_separately(project):
    make_labeled_project(project)
    v = template("eval-grade", "validate.py")
    run_py(v, "split", "--mode", "broken", cwd=project)
    run_py(v, "run", "--mode", "broken", "--split", "validation", cwd=project)
    report = json.loads((project / ".eval/default/validation/broken-validation.json").read_text())
    assert report["n"] == 0 and len(report["errors"]) > 0 and report["tpr"] is None


def test_split_cases_three_way_and_fixed_once(project):
    write_jsonl(project / ".eval/default/dataset/goldens.jsonl", [{"id": f"c{i}", "tags": ["a" if i % 2 else "b"]} for i in range(40)])
    s = template("eval-descent", "split_cases.py")
    run_py(s, cwd=project)
    split = {n: set(json.loads((project / f".eval/default/runs/{n}_ids.json").read_text())) for n in ("development", "validation", "test", "select")}
    assert len(split["development"]) + len(split["validation"]) + len(split["test"]) == 40
    assert not (split["development"] & split["validation"] or split["development"] & split["test"] or split["validation"] & split["test"])
    assert split["select"] == split["development"] | split["validation"]
    assert run_py(s, cwd=project, check=False).returncode != 0
