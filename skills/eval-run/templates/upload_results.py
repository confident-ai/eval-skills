"""Send collected outputs to Confident AI to be graded by a metric collection.

    CONFIDENT_API_KEY=... python upload_results.py --variant baseline --collection support-bot-core \
        [--param model=gpt-4.1-mini --param prompt=v3] [--region us|eu] [--dry-run]

Reads .eval/default/runs/<variant>/results.jsonl (written by run_evals.py with
--graders none) and .eval/default/dataset/goldens.jsonl, and creates one test run on
Confident AI named after the variant. Hyperparameters (--param) are attached so
runs can be compared side by side on the platform.

Part of eval-skills (Apache-2.0). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = {"us": "https://api.confident-ai.com", "eu": "https://eu.api.confident-ai.com"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def as_text(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def tool_calls(items):
    return [
        {"name": t["name"], "inputParameters": t.get("input") if isinstance(t.get("input"), dict) else None, "output": t.get("output")}
        for t in items or []
    ] or None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--variant", required=True)
    ap.add_argument("--collection", required=True, help="metric collection name on Confident AI")
    ap.add_argument("--runs", default=".eval/default/runs")
    ap.add_argument("--dataset", default=".eval/default/dataset/goldens.jsonl")
    ap.add_argument("--param", action="append", default=[], help="hyperparameter key=value (repeatable)")
    ap.add_argument("--region", choices=["us", "eu"], default=os.getenv("CONFIDENT_REGION", "us").lower())
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    goldens = {g["id"]: g for g in read_jsonl(Path(args.dataset))}
    rows = read_jsonl(Path(args.runs) / args.variant / "results.jsonl")
    if not rows:
        sys.exit(f"No results for {args.variant}; run run_evals.py --graders none first.")

    test_cases = []
    for r in rows:
        g = goldens.get(r["case_id"], {})
        case = {
            "name": f"{r['case_id']}#{r['rep']}",
            "input": as_text(r.get("input")),
            "actualOutput": as_text(r.get("output")),
            "expectedOutput": g.get("expected_output"),
            "context": g.get("context"),
            "retrievalContext": r.get("retrieval_context"),
            "toolsCalled": tool_calls(r.get("tools_called")),
            "expectedTools": tool_calls(g.get("expected_tools")),
        }
        test_cases.append({k: v for k, v in case.items() if v is not None})

    body = {
        "metricCollection": args.collection,
        "llmTestCases": test_cases,
        "identifier": args.variant,
        "hyperparameters": dict(p.split("=", 1) for p in args.param) or None,
    }
    body = {k: v for k, v in body.items() if v is not None}
    if args.dry_run:
        print(f"Would upload {len(test_cases)} test cases as '{args.variant}' against '{args.collection}'.")
        return

    key = os.getenv("CONFIDENT_API_KEY")
    if not key:
        sys.exit("Set CONFIDENT_API_KEY first (the user adds it to .env).")
    request = urllib.request.Request(
        f"{API[args.region]}/v1/evaluate",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "CONFIDENT_API_KEY": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as err:
        sys.exit(f"Upload failed ({err.code}): {err.read().decode()[:500]}")
    data = payload.get("data", payload)
    print(f"Created test run {data.get('id', '?')} for '{args.variant}' ({len(test_cases)} cases). "
          "Grading runs on Confident AI; open Test Runs in the project to follow it.")


if __name__ == "__main__":
    main()
