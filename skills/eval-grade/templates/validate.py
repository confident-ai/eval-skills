"""Measure a grader against human labels: TPR, TNR, and the disagreements.

    # 1. Draw the splits once per failure mode (development 15% / validation 45% / test 40%, stratified by label)
    python validate.py split --mode invented-policy

    # 2. Iterate on the grader against validation as often as you like
    python validate.py run --mode invented-policy --split validation

    # 3. When validation is good, measure test exactly once
    python validate.py run --mode invented-policy --split test

    # Optional: corrected pass rate on unlabeled traffic (Rogan-Gladen + bootstrap CI)
    python validate.py correct --mode invented-policy --observed-pass-rate 0.82

Labels come from .eval/default/review-app/annotations.json (review-ui label mode:
labels[mode_id] = "pass" | "fail"). Graders come from the registry
GRADERS in .eval/default/graders/graders.py (eval-skills grader contract). "Pass"
means the failure mode was NOT present; TPR is agreement on passes, TNR is
agreement on fails.

Part of eval-skills (Apache-2.0). Standard library only (plus whatever your graders import).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import inspect
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(".eval/default/validation")


# ---------------------------------------------------------------- loading ----


def load_graders(path: str) -> dict:
    spec = importlib.util.spec_from_file_location("eval_graders", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).resolve().parent))
    spec.loader.exec_module(module)
    return module.GRADERS


def load_traces(path: str) -> dict[str, dict]:
    records = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[str(record["trace_id"])] = record
    return records


def load_labels(path: str, mode_id: str) -> dict[str, str]:
    annotations = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        trace_id: a["labels"][mode_id]
        for trace_id, a in annotations.items()
        if (a.get("labels") or {}).get(mode_id) in ("pass", "fail")
    }


def trace_to_case_result(record: dict) -> tuple[dict, dict]:
    """Turn a normalized trace record into the (case, result) a grader expects."""
    steps = record.get("steps") or []
    retrieval = []
    for step in steps:
        if step.get("type") == "retriever":
            out = step.get("output")
            retrieval += [x if isinstance(x, str) else json.dumps(x) for x in (out if isinstance(out, list) else [out])]
    tools = [
        {"name": s.get("name"), "input": s.get("input"), "output": s.get("output")}
        for s in steps
        if s.get("type") == "tool"
    ]
    case = {
        "id": record["trace_id"],
        "input": record.get("input"),
        "tags": record.get("tags") or [],
        "metadata": record.get("metadata") or {},
    }
    result = {
        "output": record.get("output"),
        "retrieval_context": retrieval or None,
        "tools_called": tools or None,
        "trace_id": record["trace_id"],
    }
    return case, result


def call_grader(grader, case: dict, result: dict) -> dict:
    out = grader(case, result)
    if inspect.isawaitable(out):
        out = asyncio.run(out)
    if not isinstance(out, dict) or not isinstance(out.get("passed"), bool):
        raise TypeError(f"grader returned {out!r}; expected a dict with a boolean 'passed'")
    return out


# ------------------------------------------------------------------ stats ----


def rates(pairs: list[tuple[str, str]]) -> dict:
    tp = sum(1 for h, g in pairs if h == "pass" and g == "pass")
    fn = sum(1 for h, g in pairs if h == "pass" and g == "fail")
    tn = sum(1 for h, g in pairs if h == "fail" and g == "fail")
    fp = sum(1 for h, g in pairs if h == "fail" and g == "pass")
    return {
        "tp": tp, "fn": fn, "tn": tn, "fp": fp,
        "tpr": tp / (tp + fn) if tp + fn else None,
        "tnr": tn / (tn + fp) if tn + fp else None,
    }


def rogan_gladen(p_obs: float, tpr: float, tnr: float) -> float | None:
    denom = tpr + tnr - 1
    if abs(denom) < 1e-6:
        return None  # judge is no better than chance; no correction possible
    return min(1.0, max(0.0, (p_obs + tnr - 1) / denom))


def bootstrap_ci(pairs, p_obs, n=2000, seed=0) -> tuple[float, float] | None:
    rng = random.Random(seed)
    estimates = []
    for _ in range(n):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        r = rates(sample)
        if r["tpr"] is None or r["tnr"] is None:
            continue
        est = rogan_gladen(p_obs, r["tpr"], r["tnr"])
        if est is not None:
            estimates.append(est)
    if len(estimates) < n // 2:
        return None
    estimates.sort()
    return estimates[int(0.025 * len(estimates))], estimates[int(0.975 * len(estimates)) - 1]


# --------------------------------------------------------------- commands ----


def cmd_split(args) -> None:
    splits_path = OUT_DIR / "splits.json"
    splits = json.loads(splits_path.read_text()) if splits_path.exists() else {}
    if args.mode in splits and not args.force:
        sys.exit(f"Splits for {args.mode} already exist. Splits are fixed once drawn; pass --force only if the labels were redone.")
    labels = load_labels(args.labels, args.mode)
    from grouped_split import grouped_split
    traces = load_traces(args.traces)
    out = grouped_split([{"id":i,"group_id":traces.get(i,{}).get("group_id") or traces.get(i,{}).get("thread_id") or i} for i in labels], (.15,.45,.4), args.seed)
    splits[args.mode] = {**out, "drawn_at": datetime.now(timezone.utc).isoformat(), "test_runs": 0}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    splits_path.write_text(json.dumps(splits, indent=2))
    counts = {k: f"{sum(labels[i] == 'pass' for i in v)} pass / {sum(labels[i] == 'fail' for i in v)} fail" for k, v in out.items()}
    print(f"Splits for {args.mode}: " + "; ".join(f"{k}: {c}" for k, c in counts.items()))
    fails = sum(1 for v in labels.values() if v == "fail")
    if fails < 30 or len(labels) - fails < 30:
        print("Note: fewer than ~30 labels of each kind; TPR/TNR will have wide intervals. Label more if you can.")


def cmd_run(args) -> None:
    splits_path = OUT_DIR / "splits.json"
    splits = json.loads(splits_path.read_text())
    if args.mode not in splits:
        sys.exit(f"No splits for {args.mode}; run `split` first.")
    ids = splits[args.mode][args.split]
    if args.split == "test":
        if splits[args.mode]["test_runs"] >= 1 and not args.force:
            sys.exit("Test was already measured once. Iterate on validation; re-running test turns it into a validation set.")
        splits[args.mode]["test_runs"] += 1
        splits_path.write_text(json.dumps(splits, indent=2))
    labels = load_labels(args.labels, args.mode)
    traces = load_traces(args.traces)
    grader = load_graders(args.graders)[args.mode]

    def one(trace_id):
        case, result = trace_to_case_result(traces[trace_id])
        try:
            return trace_id, call_grader(grader, case, result), None
        except Exception as err:  # grader error, not a verdict
            return trace_id, None, f"{type(err).__name__}: {err}"

    missing = [i for i in ids if i not in traces]
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        rows = list(pool.map(one, [i for i in ids if i in traces]))
    pairs, disagreements, errors = [], [], []
    for trace_id, grade, error in rows:
        if error:
            errors.append({"trace_id": trace_id, "error": error})
            continue
        human, judged = labels[trace_id], ("pass" if grade["passed"] else "fail")
        pairs.append((human, judged))
        if human != judged:
            disagreements.append({
                "trace_id": trace_id, "human": human, "grader": judged,
                "reason": grade.get("reason"), "confidence": grade.get("confidence"),
                "kind": "false pass (too lenient)" if judged == "pass" else "false fail (too strict)",
            })
    r = rates(pairs)
    report = {"mode": args.mode, "split": args.split, "n": len(pairs), **r,
              "errors": errors, "missing_traces": missing, "disagreements": disagreements,
              "measured_at": datetime.now(timezone.utc).isoformat()}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{args.mode}-{args.split}.json").write_text(json.dumps(report, indent=2))
    fmt = lambda x: "n/a" if x is None else f"{x:.2f}"
    print(f"{args.mode} on {args.split} (n={len(pairs)}): TPR {fmt(r['tpr'])}, TNR {fmt(r['tnr'])} "
          f"| {len(disagreements)} disagreements, {len(errors)} grader errors, {len(missing)} traces missing")
    print(f"Details: {OUT_DIR / f'{args.mode}-{args.split}.json'}")


def cmd_correct(args) -> None:
    if args.observed_pass_rate is None:
        sys.exit("Pass --observed-pass-rate: the grader's pass rate on unlabeled traffic.")
    path = OUT_DIR / f"{args.mode}-test.json"
    if not path.exists():
        sys.exit("Measure the test split first; the correction uses test TPR/TNR.")
    report = json.loads(path.read_text())
    if report["tpr"] is None or report["tnr"] is None:
        sys.exit("The test split needs both human passes and human fails.")
    # Rebuild the (human, grader) pairs from the confusion counts for the bootstrap.
    pairs = (
        [("pass", "pass")] * report["tp"] + [("pass", "fail")] * report["fn"]
        + [("fail", "fail")] * report["tn"] + [("fail", "pass")] * report["fp"]
    )
    est = rogan_gladen(args.observed_pass_rate, report["tpr"], report["tnr"])
    if est is None:
        sys.exit("TPR + TNR is about 1: the grader is no better than chance, so no correction is possible.")
    ci = bootstrap_ci(pairs, args.observed_pass_rate)
    ci_text = f"95% CI {ci[0]:.2f}–{ci[1]:.2f}" if ci else "CI unavailable (too few labels)"
    print(
        f"Observed pass rate {args.observed_pass_rate:.2f} → corrected {est:.2f} ({ci_text}), "
        f"using test TPR {report['tpr']:.2f} / TNR {report['tnr']:.2f} on {len(pairs)} labeled traces."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["split", "run", "correct"])
    ap.add_argument("--mode", required=True, help="failure-mode id (key in GRADERS and in labels)")
    ap.add_argument("--split", choices=["validation", "test"], default="validation")
    ap.add_argument("--labels", default=".eval/default/review-app/annotations.json")
    ap.add_argument("--traces", default=".eval/default/traces/traces.jsonl")
    ap.add_argument("--graders", default=".eval/default/graders/graders.py")
    ap.add_argument("--observed-pass-rate", type=float)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    {"split": cmd_split, "run": cmd_run, "correct": cmd_correct}[args.command](args)


if __name__ == "__main__":
    main()
