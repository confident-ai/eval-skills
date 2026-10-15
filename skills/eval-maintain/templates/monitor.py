"""Grade a sample of recent production traces and append pass rates to a trend file.

    python monitor.py [--traces .eval/default/traces/traces.jsonl] [--since-hours 24] [--sample 200] \
        [--only invented-policy,bad-json] [--environment production]

Samples traces started within the window, runs the graders from
.eval/default/graders/graders.py (eval-skills grader contract), and appends one line
per failure mode to .eval/default/monitoring/trend.jsonl:

    {"window_end": ..., "hours": 24, "mode": "invented-policy", "n": 200, "passes": 182, "pass_rate": 0.91,
     "ci95": [0.86, 0.94], "errors": 0, "status": "ok", "alpha": 0.01,
     "reference": {"windows": 7, "n": 1400, "pass_rate": 0.92}, "delta": -0.01, "delta_upper": 0.03}

Each window is compared with a reference: the pooled counts of the last
--reference-windows usable windows for the same mode. A window is usable when it
has graded traces (at least --min-n, if set), a grader error rate of at most
--max-error-rate, and was not itself flagged. The comparison is a one-sided
test of the difference in pass rate (Newcombe's hybrid score interval, built from
Wilson intervals), valid for small windows too: a window is a regression when
the upper bound of (window - reference) at confidence 1 - alpha is below zero
and the drop is at least --min-drop.

    status        meaning                                                   exit
    ok            no significant drop against the reference                 0
    no-reference  no usable earlier window yet; this one can become one     0
    regression    significant drop; a scheduler or CI job can alert on it   2
    incomplete    grader errors above --max-error-rate, or fewer graded     3
                  traces than --min-n; not compared, never a reference

A run with any regression exits 2, otherwise 3 if any mode is incomplete.
Grader errors are provider or harness failures, not verdicts: an outage is
reported instead of passing silently, and it never becomes the baseline the next
window is compared with. Flagged windows stay out of the reference, so a lasting
regression keeps alerting instead of becoming the new normal; to accept a new
level on purpose, start a new trend file with --out.

Each mode is tested separately, so on unchanged traffic expect about
alpha x modes false alerts per window. Windows that overlap (a 24h window run
hourly) share traces and are not independent; schedule non-overlapping windows.

Part of eval-skills (Apache-2.0). Standard library only (plus your graders).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import inspect
import json
import math
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import NormalDist


def load_graders(path: str) -> dict:
    spec = importlib.util.spec_from_file_location("eval_graders", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).resolve().parent))
    spec.loader.exec_module(module)
    return module.GRADERS


def trace_to_case_result(record: dict) -> tuple[dict, dict]:
    steps = record.get("steps") or []
    retrieval = []
    for step in steps:
        if step.get("type") == "retriever":
            out = step.get("output")
            retrieval += [x if isinstance(x, str) else json.dumps(x) for x in (out if isinstance(out, list) else [out])]
    tools = [{"name": s.get("name"), "input": s.get("input"), "output": s.get("output")} for s in steps if s.get("type") == "tool"]
    case = {"id": record["trace_id"], "input": record.get("input"), "tags": record.get("tags") or [], "metadata": record.get("metadata") or {}}
    result = {"output": record.get("output"), "retrieval_context": retrieval or None, "tools_called": tools or None, "trace_id": record["trace_id"]}
    return case, result


def wilson_bounds(passes: float, n: int, z: float = 1.96) -> tuple[float, float]:
    p = passes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def wilson(passes: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None  # nothing graded: the interval is unknown, not [0, 0]
    return [round(b, 4) for b in wilson_bounds(passes, n, z)]


def drop_test(passes: int, n: int, ref_passes: int, ref_n: int, alpha: float) -> tuple[float, float]:
    """Return (window - reference) pass rate and its one-sided upper bound at confidence 1 - alpha.

    Newcombe's hybrid score interval (method 10) from the two Wilson intervals; it stays
    sensible near 0 and 1, where production pass rates usually sit.
    """
    z = NormalDist().inv_cdf(1 - alpha)
    p, q = passes / n, ref_passes / ref_n
    upper_p = wilson_bounds(passes, n, z)[1]
    lower_q = wilson_bounds(ref_passes, ref_n, z)[0]
    return p - q, p - q + math.sqrt((upper_p - p) ** 2 + (q - lower_q) ** 2)


def usable(row: dict, min_n: int, max_error_rate: float) -> bool:
    """Whether an earlier trend row can serve as reference. Rows written before statuses existed are judged by their counts."""
    if row.get("status") in ("regression", "incomplete"):
        return False
    n, errors = row.get("n") or 0, row.get("errors") or 0
    return n >= max(min_n, 1) and row.get("pass_rate") is not None and errors / (n + errors) <= max_error_rate


def passes_of(row: dict) -> int:
    return row["passes"] if isinstance(row.get("passes"), int) else round(row["pass_rate"] * row["n"])


def call(grader, case, result) -> dict:
    out = grader(case, result)
    if inspect.isawaitable(out):
        out = asyncio.run(out)
    if not isinstance(out, dict) or not isinstance(out.get("passed"), bool):
        raise TypeError(f"grader returned {out!r}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces", default=".eval/default/traces/traces.jsonl")
    ap.add_argument("--graders", default=".eval/default/graders/graders.py")
    ap.add_argument("--out", default=".eval/default/monitoring/trend.jsonl")
    ap.add_argument("--since-hours", type=float, default=24)
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--only", help="comma-separated grader ids (skip graders that need expected_output)")
    ap.add_argument("--environment", default=None, help="keep traces whose metadata.environment matches")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--reference-windows", type=int, default=7, help="usable earlier windows pooled into the reference")
    ap.add_argument("--alpha", type=float, default=0.01, help="one-sided false-alert rate per mode per window")
    ap.add_argument("--min-drop", type=float, default=0.0, help="smallest drop in pass rate worth alerting on, e.g. 0.03")
    ap.add_argument("--min-n", type=int, default=1, help="policy floor: graded traces needed to compare a window or use it as reference")
    ap.add_argument("--max-error-rate", type=float, default=0.1, help="grader error share above which a window is incomplete")
    args = ap.parse_args()
    # Exit 1, not argparse's 2: exit 2 means "regression" to the scheduler.
    if not 0 < args.alpha < 0.5:
        sys.exit("--alpha must be between 0 and 0.5")
    if args.reference_windows < 1:
        sys.exit("--reference-windows must be at least 1")

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=args.since_hours)
    traces = []
    for line in Path(args.traces).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        started = datetime.fromisoformat(str(t.get("started_at", "")).replace("Z", "+00:00")) if t.get("started_at") else None
        if started and started >= since and (not args.environment or (t.get("metadata") or {}).get("environment") == args.environment):
            traces.append(t)
    rng = random.Random(args.seed)
    sample = rng.sample(traces, k=min(args.sample, len(traces)))
    graders = load_graders(args.graders)
    if args.only:
        graders = {k: v for k, v in graders.items() if k in set(args.only.split(","))}
    if not sample:
        print(f"No traces in the last {args.since_hours:g}h; nothing graded.")
        return

    def grade_all(trace):
        case, result = trace_to_case_result(trace)
        out = {}
        for mode_id, grader in graders.items():
            try:
                out[mode_id] = call(grader, case, result)["passed"]
            except Exception:
                out[mode_id] = None  # grader error: counted separately, never as a fail
        return out

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        verdicts = list(pool.map(grade_all, sample))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    history: dict[str, list[dict]] = {}
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                history.setdefault(row["mode"], []).append(row)

    regressed = incomplete = False
    with out_path.open("a", encoding="utf-8") as f:
        for mode_id in graders:
            graded = [v[mode_id] for v in verdicts if v[mode_id] is not None]
            n, passes = len(graded), sum(graded)
            errors = len(verdicts) - n
            row = {
                "window_end": now.isoformat(), "hours": args.since_hours, "mode": mode_id, "n": n, "passes": passes,
                "pass_rate": round(passes / n, 4) if n else None, "ci95": wilson(passes, n), "errors": errors,
                "status": None, "alpha": args.alpha, "reference": None, "delta": None, "delta_upper": None,
            }
            reference = [r for r in history.get(mode_id, []) if usable(r, args.min_n, args.max_error_rate)][-args.reference_windows:]
            if n < max(args.min_n, 1) or errors / len(verdicts) > args.max_error_rate:
                row["status"] = "incomplete"
            elif not reference:
                row["status"] = "no-reference"
            else:
                ref_passes, ref_n = sum(passes_of(r) for r in reference), sum(r["n"] for r in reference)
                delta, upper = drop_test(passes, n, ref_passes, ref_n, args.alpha)
                row["reference"] = {"windows": len(reference), "n": ref_n, "pass_rate": round(ref_passes / ref_n, 4)}
                row["delta"], row["delta_upper"] = round(delta, 4), round(upper, 4)
                row["status"] = "regression" if upper < 0 and -delta >= args.min_drop else "ok"
            f.write(json.dumps(row) + "\n")

            rate = "n/a" if row["pass_rate"] is None else f"{row['pass_rate']:.2f}"
            ci = "" if row["ci95"] is None else f"95% CI {row['ci95'][0]:.2f}–{row['ci95'][1]:.2f}, "
            line = f"{mode_id}: {rate} ({ci}n={n}, errors={errors})"
            if row["status"] == "incomplete":
                incomplete = True
                line += (f"  ⚠ incomplete: {n} graded, {errors} grader errors (needs n ≥ {max(args.min_n, 1)} and ≤ "
                         f"{args.max_error_rate:.0%} errors); not compared and not used as a reference")
            elif row["status"] == "no-reference":
                line += "  no usable earlier window yet; this window can serve as the reference"
            else:
                ref = row["reference"]
                line += (f" vs reference {ref['pass_rate']:.2f} ({ref['windows']} window(s), n={ref['n']}): "
                         f"Δ {row['delta']:+.2f}, upper bound {row['delta_upper']:+.2f} at {100 * (1 - args.alpha):g}%")
                if row["status"] == "regression":
                    regressed = True
                    line += "  ⚠ regression"
            print(line)
    if regressed:
        sys.exit(2)
    if incomplete:
        sys.exit(3)


if __name__ == "__main__":
    main()
