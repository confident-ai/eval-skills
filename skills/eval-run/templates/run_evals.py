"""Run the app over the dataset, grade every output, and report with confidence intervals.

    python run_evals.py --variant baseline --reps 2                  # full run (resumable)
    python run_evals.py --variant baseline --reps 2 --dry-run        # print the resolved scope only
    python run_evals.py --variant v1 --reps 2 --compare baseline     # paired comparison against a frozen baseline
    python run_evals.py --variant v1 --ids .eval/default/runs/test_ids.json  # restrict to a split (held-out test, etc.)
    python run_evals.py --variant v2 --ids .eval/default/runs/select_ids.json --compare baseline --compare-ids .eval/default/runs/validation_ids.json

Reads cases from .eval/default/dataset/goldens.jsonl, calls run_case() from
.eval/default/scripts/app_adapter.py, applies every grader in GRADERS
(.eval/default/graders/graders.py), and writes to .eval/default/runs/<variant>/:

    results.jsonl   one row per (case, rep), appended as each finishes. Each row carries a hash of
                    its case and of the harness (adapter, graders, app code in git); resume skips
                    only rows whose hashes still match, and refuses to mix in stale rows
    errors.jsonl    one row per failed attempt (app or grader), with a failure class; never scored
    summary.json    pass rates with 95% intervals computed over cases (repetitions are averaged
                    within a case first), per failure mode and per tag, plus latency

Properties: bounded concurrency, per-call soft timeouts (provider cancellation is separate), jittered
backoff on rate limits and overloads, attempts that failed only on retry are
recorded, and a grader exception is an error, not a failing verdict.

Part of eval-skills (Apache-2.0). Standard library only (plus your app and graders).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import inspect
import json
import math
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RETRYABLE_HINTS = ("ratelimit", "rate_limit", "overloaded", "429", "503", "529", "apiconnection", "temporarily")


def load_attr(path_colon_name: str):
    path, _, name = path_colon_name.partition(":")
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).resolve().parent))
    spec.loader.exec_module(module)
    return getattr(module, name)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def case_hash(case: dict) -> str:
    return _sha(json.dumps(case, sort_keys=True, ensure_ascii=False, default=str).encode())


def _git_state() -> str:
    """HEAD plus a hash of uncommitted changes outside .eval/default/ (eval files are hashed directly)."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        diff = subprocess.run(
            ["git", "diff", "HEAD", "--no-ext-diff", "--", ".", ":(exclude).eval"], capture_output=True, check=True
        ).stdout
        return f"{head}:{_sha(diff)}"
    except (OSError, subprocess.CalledProcessError):
        return "no-git"


def harness_hash(args) -> str:
    """Identifies the code that produced a row: adapter, graders module and its siblings, app code in git."""
    h = hashlib.sha256()
    paths = [Path(args.app.partition(":")[0])]
    if args.graders != "none":
        g = Path(args.graders)
        paths += sorted(p for p in g.parent.glob(f"*{g.suffix}") if p.is_file())
    for p in paths:
        h.update(p.name.encode())
        h.update(p.read_bytes() if p.exists() else b"")
    h.update(json.dumps({"reps":args.reps,"timeout":args.timeout_s,"max_attempts":args.max_attempts,"config":json.loads(Path(args.config).read_text()) if args.config else None},sort_keys=True).encode())
    h.update(f"only={args.only}|app-version={args.app_version or _git_state()}".encode())
    return h.hexdigest()[:16]


def classify(error: BaseException) -> str:
    text = f"{type(error).__name__} {error}".lower()
    if isinstance(error, asyncio.TimeoutError | TimeoutError):
        return "timeout"
    if any(h in text for h in RETRYABLE_HINTS):
        return "rate-limit"
    if "refus" in text or "content_filter" in text or "safety" in text:
        return "refusal"
    return "harness"


def wilson(passes: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = passes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


async def call_maybe_async(fn, *args):
    if inspect.iscoroutinefunction(fn):
        return await fn(*args)
    out = await asyncio.to_thread(fn, *args)
    return await out if inspect.isawaitable(out) else out


async def run_one(case, rep, run_case, graders, args, results_path, errors_path, sem, hashes):
    async with sem:
        started = time.monotonic()
        attempts = 0
        while True:
            attempts += 1
            ledger = results_path.parent / "attempts.jsonl"
            attempt_id = sum(1 for a in read_jsonl(ledger) if a["case_id"] == case["id"] and a["rep"] == rep) + 1
            try:
                result = await asyncio.wait_for(call_maybe_async(run_case, {k: case[k] for k in ("id", "input", "scenario", "attachments") if k in case}), timeout=args.timeout_s)
                append_jsonl(ledger, {"case_id":case["id"], "rep":rep,"attempt":attempt_id,"stage":"app","status":"ok","usage":result.get("usage"),"cost_usd":result.get("cost_usd")})
                break
            except BaseException as err:  # noqa: BLE001 - classify everything from the app
                if isinstance(err, KeyboardInterrupt | asyncio.CancelledError):
                    raise
                kind = classify(err)
                append_jsonl(ledger,{"case_id":case["id"],"rep":rep,"attempt":attempt_id,"stage":"app","status":kind,"usage":getattr(err,"usage",None),"cost_usd":getattr(err,"cost_usd",None)})
                append_jsonl(errors_path, {
                    "case_id": case["id"], "rep": rep, "stage": "app", "failure_class": kind,
                    "attempt": attempts, "error": f"{type(err).__name__}: {err}"[:2000],
                    "at": datetime.now(timezone.utc).isoformat(),
                })
                if kind == "rate-limit" and attempts < args.max_attempts:
                    await asyncio.sleep(min(60.0, 2**attempts) * (0.5 + random.random()))
                    continue
                return None
        latency = time.monotonic() - started

        grades, grader_errors = {}, []
        for mode_id, grader in graders.items():
            try:
                grade = await asyncio.wait_for(call_maybe_async(grader, case, result), timeout=args.timeout_s)
                if not isinstance(grade, dict) or not isinstance(grade.get("passed"), bool):
                    raise TypeError(f"grader returned {grade!r}")
                grades[mode_id] = grade
                append_jsonl(ledger,{"case_id":case["id"],"rep":rep,"attempt":sum(1 for a in read_jsonl(ledger) if a["case_id"]==case["id"] and a["rep"]==rep)+1,"stage":"judge","grader":mode_id,"status":"ok","usage":grade.get("usage"),"cost_usd":grade.get("cost_usd")})
            except BaseException as err:  # noqa: BLE001
                if isinstance(err, KeyboardInterrupt | asyncio.CancelledError):
                    raise
                grader_errors.append(mode_id)
                append_jsonl(ledger,{"case_id":case["id"],"rep":rep,"attempt":sum(1 for a in read_jsonl(ledger) if a["case_id"]==case["id"] and a["rep"]==rep)+1,"stage":"judge","grader":mode_id,"status":classify(err),"usage":getattr(err,"usage",None),"cost_usd":getattr(err,"cost_usd",None)})
                append_jsonl(errors_path, {
                    "case_id": case["id"], "rep": rep, "stage": "grader", "grader": mode_id,
                    "failure_class": classify(err), "error": f"{type(err).__name__}: {err}"[:2000],
                    "at": datetime.now(timezone.utc).isoformat(),
                })
        if grader_errors:
            return None  # leave the (case, rep) slot empty so a resume re-runs it

        row = {
            "case_id": case["id"], "group_id": case.get("group_id", case["id"]), "rep": rep, "tags": case.get("tags") or [],
            "input": case.get("input", case.get("scenario")), "output": result.get("output"),
            **{k: result[k] for k in ("retrieval_context", "tools_called", "turns") if result.get(k)},
            "grades": grades, "passed_all": all(g["passed"] for g in grades.values()),
            "latency_s": round(latency, 3), "attempts": attempts,
            "trace": result.get("trace"), "model": result.get("model"), "usage": result.get("usage"), "trace_id": result.get("trace_id"),
            "case_hash": hashes["case"][case["id"]], "harness_hash": hashes["harness"],
            "at": datetime.now(timezone.utc).isoformat(),
        }
        append_jsonl(results_path, row)
        return row


def case_level(rows: list[dict], value) -> dict:
    """Average repetitions within each case, then put the interval over cases.

    Repetitions of one case are not independent evidence about the app, so the
    interval must not narrow just because reps were added.
    """
    by_case: dict[str, list[float]] = {}
    for r in rows:
        v = value(r)
        if v is not None:
            by_case.setdefault(r.get("group_id", r["case_id"]), []).append(float(v))
    means = [sum(v) / len(v) for v in by_case.values()]
    if not means:
        return {"pass_rate": None, "ci95": [None, None], "n_cases": 0, "n_runs": 0}
    p = sum(means) / len(means)
    lo, hi = wilson(p * len(means), len(means))
    return {"pass_rate": p, "ci95": [lo, hi], "n_cases": len(means), "n_runs": sum(len(v) for v in by_case.values())}


def usage_summary(values):
    return {k: sum(v[k] for v in values if isinstance(v, dict) and isinstance(v.get(k), (int, float)) and not isinstance(v[k], bool))
            if any(isinstance(v, dict) and isinstance(v.get(k), (int, float)) and not isinstance(v[k], bool) for v in values) else None
            for k in ("input_tokens", "output_tokens")}


def summarize(rows: list[dict], errors: list[dict], n_cases: int, reps: int) -> dict:
    modes = sorted({m for r in rows for m in r["grades"]})
    per_mode = {m: case_level(rows, lambda r, m=m: r["grades"][m]["passed"] if m in r["grades"] else None) for m in modes}
    overall = case_level(rows, lambda r: r["passed_all"])
    per_tag: dict[str, list[dict]] = {}
    for r in rows:
        per_tag.setdefault((r["tags"] or ["untagged"])[0], []).append(r)
    latencies = sorted(r["latency_s"] for r in rows)
    pct = lambda q: latencies[min(len(latencies) - 1, int(q * len(latencies)))] if latencies else None
    tokens = [r["usage"] for r in rows if isinstance(r.get("usage"), dict)]
    return {
        "cases": n_cases, "reps": reps, "rows": len(rows),
        "pass_rate_all": overall["pass_rate"], "ci95_all": overall["ci95"], "cases_scored": overall["n_cases"],
        "interval_method": "Wilson approximation over independent groups; repetitions and related cases averaged within each group",
        "noise_floor_approx": 1 / math.sqrt(overall["n_cases"]) if overall["n_cases"] else None,
        "per_failure_mode": per_mode,
        "per_tag": {t: case_level(rs, lambda r: r["passed_all"]) for t, rs in per_tag.items()},
        "latency_s": {"p50": pct(0.5), "p95": pct(0.95)},
        "usage_totals": usage_summary([r.get("usage") for r in rows]),
        "usage_complete": len(tokens) == len(rows) and bool(rows) and all(all(u.get(k) is not None for k in ("input_tokens", "output_tokens")) for u in tokens),
        "models_seen": sorted({r["model"] for r in rows if r.get("model")}),
        "errors": {"app": sum(e["stage"] == "app" for e in errors), "grader": sum(e["stage"] == "grader" for e in errors)},
        "missing_slots": n_cases * reps - len(rows),
    }


def compare(variant_rows: list[dict], baseline_rows: list[dict], seed: int = 0) -> dict:
    """Paired difference in pass rate (passed_all) over cases present in both runs."""

    def per_case(rows):
        out: dict[str, list[int]] = {}
        for r in rows:
            out.setdefault(r.get("group_id", r["case_id"]), []).append(int(r["passed_all"]))
        return {k: sum(v) / len(v) for k, v in out.items()}

    a, b = per_case(variant_rows), per_case(baseline_rows)
    shared = sorted(set(a) & set(b))
    diffs = [a[c] - b[c] for c in shared]
    if not diffs:
        return {"n_cases": 0}
    rng = random.Random(seed)
    boots = sorted(sum(diffs[rng.randrange(len(diffs))] for _ in diffs) / len(diffs) for _ in range(2000))
    lo, hi = boots[50], boots[1949]
    return {
        "n_cases": len(shared), "delta": sum(diffs) / len(diffs), "ci95": [lo, hi],
        "verdict": "better" if lo > 0 else "worse" if hi < 0 else "within noise",
        "flipped_to_pass": [c for c in shared if a[c] > b[c]], "flipped_to_fail": [c for c in shared if a[c] < b[c]],
    }


async def main_async(args) -> None:
    cases = read_jsonl(Path(args.dataset))
    if args.ids:
        keep = set(json.loads(Path(args.ids).read_text()))
        cases = [c for c in cases if c["id"] in keep]
    if args.limit:
        cases = cases[: args.limit]
    out_dir = Path(args.out) / args.variant
    results_path, errors_path = out_dir / "results.jsonl", out_dir / "errors.jsonl"
    hashes = {"case": {c["id"]: case_hash(c) for c in cases}, "harness": harness_hash(args)}

    # Resume only from rows produced by these exact cases and this exact harness.
    existing = read_jsonl(results_path)
    in_scope = [r for r in existing if r["case_id"] in hashes["case"]]
    stale = [r for r in in_scope
             if r.get("case_hash") != hashes["case"][r["case_id"]] or r.get("harness_hash") != hashes["harness"]]
    if stale and not args.dry_run:
        if not args.discard_stale:
            sys.exit(
                f"{len(stale)} rows in {results_path} came from a different case definition, app, or grader "
                "version, so resuming would mix old results into this run. Use a new --variant for the "
                "changed code, or pass --discard-stale to move them to stale.jsonl and re-run those slots."
            )
        stale_ids = {id(r) for r in stale}
        with (out_dir / "stale.jsonl").open("a", encoding="utf-8") as f:
            for r in stale:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        results_path.write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n"
                                        for r in existing if id(r) not in stale_ids), encoding="utf-8")
    stale_keys = {(r["case_id"], r["rep"]) for r in stale}
    done = {(r["case_id"], r["rep"]) for r in in_scope} - stale_keys
    todo = [(c, rep) for c in cases for rep in range(args.reps) if (c["id"], rep) not in done]

    # --graders none collects outputs only (managed track: graders run on Confident AI).
    graders = {} if args.graders == "none" else load_attr(f"{args.graders}:GRADERS")
    if args.only:
        graders = {k: v for k, v in graders.items() if k in set(args.only.split(","))}
    print(f"Scope: {len(cases)} cases × {args.reps} reps = {len(cases) * args.reps} slots "
          f"({len(done)} already done, {len(todo)} to run); graders: {', '.join(graders) or 'none'}; "
          f"concurrency {args.concurrency}; per-call soft timeout {args.timeout_s}s → {out_dir}"
          + (f"; {len(stale)} stale rows would block a resume" if stale else ""))
    if args.dry_run:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    run_case = load_attr(args.app)
    sem = asyncio.Semaphore(args.concurrency)
    tasks = [asyncio.create_task(run_one(c, rep, run_case, graders, args, results_path, errors_path, sem, hashes))
             for c, rep in todo]
    last = time.monotonic()
    for i, task in enumerate(asyncio.as_completed(tasks), 1):
        await task
        if time.monotonic() - last > 15 or i == len(tasks):
            print(f"  {i}/{len(tasks)} done", flush=True)
            last = time.monotonic()

    rows = [r for r in read_jsonl(results_path)
            if hashes["case"].get(r["case_id"]) == r.get("case_hash") and r.get("harness_hash") == hashes["harness"]]
    if not graders:
        print(f"\nCollected outputs for {len(rows)} of {len(cases) * args.reps} slots in {results_path}. "
              "Upload them for grading with upload_results.py.")
        return
    summary = summarize(rows, read_jsonl(errors_path), len(cases), args.reps)
    ledger = read_jsonl(out_dir / "attempts.jsonl")
    summary["usage_by_stage"] = {stage: {"measured_tokens":usage_summary([a.get("usage") for a in ledger if a["stage"]==stage]), "calls":sum(a["stage"]==stage for a in ledger), "missing_usage_calls":sum(a["stage"]==stage and a.get("usage") is None for a in ledger)} for stage in ("app","judge")}
    if args.compare:
        base_rows = read_jsonl(Path(args.out) / args.compare / "results.jsonl")
        mine = rows
        if args.compare_ids:  # decide on a subset (e.g. validation) even when the run covers more
            keep = set(json.loads(Path(args.compare_ids).read_text()))
            mine = [r for r in rows if r["case_id"] in keep]
            base_rows = [r for r in base_rows if r["case_id"] in keep]
        summary["compare"] = {"baseline": args.compare, "ids": args.compare_ids, **compare(mine, base_rows)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    fmt = lambda x: "n/a" if x is None else f"{x:.2f}"
    lo, hi = summary["ci95_all"]
    print(f"\n{args.variant}: all graders pass {fmt(summary['pass_rate_all'])} over {summary['cases_scored']} cases "
          f"({summary['rows']} runs; 95% CI over cases {fmt(lo)}–{fmt(hi)}; noise ≈ ±{fmt(summary['noise_floor_approx'])})")
    for m, s in summary["per_failure_mode"].items():
        print(f"  {m}: {fmt(s['pass_rate'])} (95% CI {fmt(s['ci95'][0])}–{fmt(s['ci95'][1])}, {s['n_cases']} cases)")
    if summary["missing_slots"]:
        print(f"  {summary['missing_slots']} slots missing: see errors.jsonl; re-run the same command to retry them.")
    if "compare" in summary and summary["compare"].get("n_cases"):
        c = summary["compare"]
        print(f"  vs {args.compare}: Δ {c['delta']:+.2f} (95% CI {c['ci95'][0]:+.2f} to {c['ci95'][1]:+.2f}) → {c['verdict']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--variant", required=True, help="run name: baseline, v1, v2, ...")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--dataset", default=".eval/default/dataset/goldens.jsonl")
    ap.add_argument("--app", default=".eval/default/scripts/app_adapter.py:run_case")
    ap.add_argument("--graders", default=".eval/default/graders/graders.py", help='path, or "none" to collect outputs only')
    ap.add_argument("--out", default=".eval/default/runs")
    ap.add_argument("--ids", help="JSON list of case ids to restrict to (for splits)")
    ap.add_argument("--only", help="comma-separated grader ids to run")
    ap.add_argument("--limit", type=int, help="first N cases only (pilot runs)")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--timeout-s", type=float, default=180.0)
    ap.add_argument("--max-attempts", type=int, default=4)
    ap.add_argument("--compare", help="variant to compare against (paired, per case)")
    ap.add_argument("--compare-ids", help="JSON list of case ids the comparison is restricted to (e.g. validation_ids.json)")
    ap.add_argument("--config", help="JSON run settings to fingerprint (model, judge, fixtures; no secrets)")
    ap.add_argument("--app-version", help="identifies the app code in run fingerprints (default: git HEAD + uncommitted diff)")
    ap.add_argument("--discard-stale", action="store_true", help="move rows from older code or cases to stale.jsonl and re-run them")
    ap.add_argument("--dry-run", action="store_true")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
