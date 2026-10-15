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


def _grouped_split():
    import importlib.util
    spec = importlib.util.spec_from_file_location("grouped_split", template("eval-grade", "grouped_split.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.grouped_split


def test_grouped_split_without_strata_keeps_existing_partitions():
    split = _grouped_split()([{"id": f"c{i:02d}", "group_id": f"g{i // 2}"} for i in range(12)])
    assert split == {"development": ["c04", "c05", "c10", "c11"], "validation": ["c00", "c01", "c02", "c03"],
                     "test": ["c06", "c07", "c08", "c09"]}


def test_grouped_split_stratifies_a_rare_label_across_every_split():
    grouped_split = _grouped_split()
    for seed in range(50):
        records = [{"id": f"t{i:02d}", "stratum": "fail" if i % 7 == seed % 7 else "pass"} for i in range(42)]
        split = grouped_split(records, (.15, .45, .4), seed)
        fails = {k: sum(r["stratum"] == "fail" for r in records if r["id"] in v) for k, v in split.items()}
        assert fails == {"development": 1, "validation": 3, "test": 2}, (seed, fails)  # targets 0.9 / 2.7 / 2.4
        assert [len(v) for v in split.values()] == [6, 19, 17]


def test_grouped_split_keeps_groups_whole_while_covering_mixed_labels():
    records = [{"id": f"t{i:02d}", "group_id": f"thread{i // 3}", "stratum": "fail" if i % 9 == 0 else "pass"} for i in range(54)]
    split = _grouped_split()(records, (.15, .45, .4), 3)
    group = {r["id"]: r["group_id"] for r in records}
    label = {r["id"]: r["stratum"] for r in records}
    where = {}
    for name, ids in split.items():
        assert all(where.setdefault(group[i], name) == name for i in ids)  # a thread never crosses splits
        assert any(label[i] == "fail" for i in ids), f"{name} has no fail"


def test_grouped_split_pools_strata_too_small_to_spread():
    split = _grouped_split()([{"id": f"c{i:02d}", "stratum": f"unique-{i}"} for i in range(40)])
    assert [len(v) for v in split.values()] == [16, 12, 12]  # sizes stay on target instead of piling into one split


def test_validate_split_is_stratified_by_label(project):
    make_labeled_project(project)
    out = run_py(template("eval-grade", "validate.py"), "split", "--mode", "invented-policy", cwd=project)
    splits = json.loads((project / ".eval/default/validation/splits.json").read_text())["invented-policy"]
    labels = {t: a["labels"]["invented-policy"] for t, a in json.loads((project / ".eval/default/review-app/annotations.json").read_text()).items()}
    fails = {k: sum(labels[i] == "fail" for i in splits[k]) for k in ("development", "validation", "test")}
    assert fails == {"development": 3, "validation": 10, "test": 9}  # 22 fails at 15/45/40
    assert "has no" not in out.stdout


def test_split_cases_stratifies_by_first_tag(project):
    tags = ["billing"] * 24 + ["refund"] * 12 + ["legal"] * 4
    write_jsonl(project / ".eval/default/dataset/goldens.jsonl", [{"id": f"c{i:02d}", "tags": [t]} for i, t in enumerate(tags)])
    run_py(template("eval-descent", "split_cases.py"), cwd=project)
    for name, share in (("development", .4), ("validation", .3), ("test", .3)):
        ids = json.loads((project / f".eval/default/runs/{name}_ids.json").read_text())
        per_tag = {t: sum(tags[int(i[1:])] == t for i in ids) for t in ("billing", "refund", "legal")}
        assert per_tag["legal"] >= 1 and abs(per_tag["billing"] - 24 * share) <= 1 and abs(per_tag["refund"] - 12 * share) <= 1, (name, per_tag)
