"""Grade a sample of recent production traces and append pass rates to a trend file.

    python monitor.py [--traces .eval/default/traces/traces.jsonl] [--since-hours 24] [--sample 200] \
        [--only invented-policy,bad-json] [--environment production]

Samples traces started within the window, runs the graders from
.eval/default/graders/graders.py (eval-skills grader contract), and appends one line
per failure mode to .eval/default/monitoring/trend.jsonl:

    {"window_end": ..., "hours": 24, "mode": "invented-policy", "n": 200, "pass_rate": 0.91, "ci95": [0.86, 0.94], "errors": 0}

Exits with status 2 and prints a warning when a failure mode's pass rate falls
below the lower bound of its previous window's interval, so a scheduler or CI
job can alert on it.

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


def wilson(passes: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p = passes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


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
    args = ap.parse_args()

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
    previous: dict[str, dict] = {}
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                previous[row["mode"]] = row

    alert = False
    with out_path.open("a", encoding="utf-8") as f:
        for mode_id in graders:
            graded = [v[mode_id] for v in verdicts if v[mode_id] is not None]
            passes = sum(graded)
            row = {
                "window_end": now.isoformat(), "hours": args.since_hours, "mode": mode_id, "n": len(graded),
                "pass_rate": round(passes / len(graded), 4) if graded else None, "ci95": wilson(passes, len(graded)),
                "errors": sum(v[mode_id] is None for v in verdicts),
            }
            f.write(json.dumps(row) + "\n")
            prev = previous.get(mode_id)
            flag = ""
            if prev and row["pass_rate"] is not None and prev.get("ci95") and row["pass_rate"] < prev["ci95"][0]:
                flag, alert = "  ⚠ below last window's interval", True
            rate = "n/a" if row["pass_rate"] is None else f"{row['pass_rate']:.2f}"
            print(f"{mode_id}: {rate} (95% CI {row['ci95'][0]:.2f}–{row['ci95'][1]:.2f}, n={row['n']}, errors={row['errors']}){flag}")
    if alert:
        sys.exit(2)


if __name__ == "__main__":
    main()
