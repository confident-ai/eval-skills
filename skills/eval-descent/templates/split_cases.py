"""Split dataset cases into development, validation, and test once, stratified by tags[0].

    python split_cases.py [--dataset .eval/default/dataset/goldens.jsonl] [--fractions 0.4 0.3 0.3] [--seed 7]

Writes to .eval/default/runs/:

    development_ids.json   cases whose outputs and traces you read to decide what to change
    validation_ids.json     cases scored each round to decide keep or revert (never read)
    test_ids.json    cases scored once, at the end, on the baseline and the final version
    select_ids.json  development + validation, the set every round runs on

Refuses to overwrite an existing split. The split is fixed for the whole
improvement loop; don't redraw it because scores look uneven, since choosing a
split by its scores is itself a form of tuning.

Part of eval-skills (Apache-2.0). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

NAMES = ("development", "validation", "test")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataset", default=".eval/default/dataset/goldens.jsonl")
    ap.add_argument("--out", default=".eval/default/runs")
    ap.add_argument("--fractions", type=float, nargs=3, default=(0.4, 0.3, 0.3), metavar=("TRAIN", "DEV", "TEST"))
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    out = Path(args.out)
    paths = {name: out / f"{name}_ids.json" for name in (*NAMES, "select")}
    if any(p.exists() for p in paths.values()):
        sys.exit("A split already exists. Keep it for the whole loop; delete all four files only to start a new loop from scratch.")
    total = sum(args.fractions)
    fractions = [f / total for f in args.fractions]

    cases = [json.loads(l) for l in Path(args.dataset).read_text(encoding="utf-8").splitlines() if l.strip()]
    from grouped_split import grouped_split
    split = grouped_split(cases, fractions, args.seed)

    out.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        paths[name].write_text(json.dumps(sorted(split[name]), indent=2))
    paths["select"].write_text(json.dumps(sorted(split["development"] + split["validation"]), indent=2))
    print(
        f"development: {len(split['development'])}, validation: {len(split['validation'])}, test: {len(split['test'])} cases "
        f"group-disjoint → {out}/{{development,validation,test,select}}_ids.json"
    )
    if len(split["validation"]) < 20 or len(split["test"]) < 20:
        print("Note: validation or test has fewer than 20 cases; intervals will be wide (about ±1/sqrt(cases)).")


if __name__ == "__main__":
    main()
