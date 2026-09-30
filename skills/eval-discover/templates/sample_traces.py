"""Pick a diverse sample of traces to review.

    python sample_traces.py --traces .eval/default/traces/traces.jsonl --n 25 \
        [--exclude .eval/default/review-app/annotations.json] [--out .eval/default/review-app/samples.json] [--seed 7]

The sample mixes three sources so review finds different failures, not the
same one many times:

- random picks (about a third): the only unbiased view of normal traffic;
- cluster representatives: traces nearest the centre of each group of
  structurally similar traces (length, steps, tool calls, latency, tokens);
- structural outliers: the slowest, longest, most tool-heavy, and errored
  traces, plus any with negative user feedback in metadata.

Already-reviewed trace ids (keys of annotations.json) are skipped. Appends to
an existing samples.json so the reviewer's queue grows instead of resetting.

Part of eval-skills (Apache-2.0). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path


def features(t: dict) -> list[float]:
    steps = t.get("steps") or []
    text_len = len(json.dumps(t.get("input"), default=str)) + len(json.dumps(t.get("output"), default=str))
    tokens = sum((s.get("input_tokens") or 0) + (s.get("output_tokens") or 0) for s in steps)
    return [
        math.log1p(text_len),
        float(len(steps)),
        float(sum(1 for s in steps if s.get("type") == "tool")),
        float(sum(1 for s in steps if s.get("type") == "retriever")),
        math.log1p(t.get("duration_ms") or 0),
        math.log1p(tokens),
    ]


def standardize(rows: list[list[float]]) -> list[list[float]]:
    cols = list(zip(*rows))
    means = [sum(c) / len(c) for c in cols]
    stds = [math.sqrt(sum((x - m) ** 2 for x in c) / len(c)) or 1.0 for c, m in zip(cols, means)]
    return [[(x - m) / s for x, m, s in zip(r, means, stds)] for r in rows]


def dist(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def kmeans(
    points: list[list[float]], k: int, rng: random.Random, iters: int = 25
) -> tuple[list[int], list[list[float]]]:
    centers = [points[rng.randrange(len(points))]]
    while len(centers) < k:  # k-means++ seeding
        weights = [min(dist(p, c) for c in centers) for p in points]
        total = sum(weights) or 1.0
        r, acc = rng.random() * total, 0.0
        for p, w in zip(points, weights):
            acc += w
            if acc >= r:
                centers.append(p)
                break
    assign = [0] * len(points)
    for _ in range(iters):
        assign = [min(range(k), key=lambda j: dist(p, centers[j])) for p in points]
        for j in range(k):
            members = [p for p, a in zip(points, assign) if a == j]
            if members:
                centers[j] = [sum(col) / len(members) for col in zip(*members)]
    return assign, centers


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces", default=".eval/default/traces/traces.jsonl")
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--exclude", default=".eval/default/review-app/annotations.json")
    ap.add_argument("--out", default=".eval/default/review-app/samples.json")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    traces = [json.loads(l) for l in Path(args.traces).read_text(encoding="utf-8").splitlines() if l.strip()]
    out_path = Path(args.out)
    existing = json.loads(out_path.read_text()) if out_path.exists() else []
    reviewed = set(json.loads(Path(args.exclude).read_text())) if Path(args.exclude).exists() else set()
    skip = reviewed | set(existing)
    pool = [t for t in traces if t["trace_id"] not in skip]
    if not pool:
        print("No unreviewed traces left.")
        return

    n = min(args.n, len(pool))
    picked: dict[str, str] = {}

    def take(trace_id: str, why: str) -> None:
        if len(picked) < n and trace_id not in picked:
            picked[trace_id] = why

    # Outliers first: a few, so they don't crowd out normal traffic.
    by = lambda key: sorted(pool, key=key, reverse=True)[:1]
    for t in [t for t in pool if t.get("error")][:2]:
        take(t["trace_id"], "errored")
    for t in [t for t in pool if str((t.get("metadata") or {}).get("feedback", "")).lower() in {"negative", "thumbs_down", "0", "bad"}][:3]:
        take(t["trace_id"], "negative feedback")
    for t in by(lambda t: t.get("duration_ms") or 0):
        take(t["trace_id"], "slowest")
    for t in by(lambda t: len(t.get("steps") or [])):
        take(t["trace_id"], "most steps")

    # Random third.
    for t in rng.sample(pool, k=min(len(pool), max(1, n // 3))):
        take(t["trace_id"], "random")

    # Cluster representatives for the rest.
    if len(pool) >= 8 and len(picked) < n:
        k = max(2, min(10, (n - len(picked)), len(pool) // 4))
        pts = standardize([features(t) for t in pool])
        assign, centers = kmeans(pts, k, rng)
        order = sorted(range(len(pool)), key=lambda i: dist(pts[i], centers[assign[i]]))
        seen: set[int] = set()
        for i in order:
            if assign[i] not in seen:
                seen.add(assign[i])
                take(pool[i]["trace_id"], f"cluster {assign[i]} representative")
    for t in rng.sample(pool, k=len(pool)):  # top up with random picks
        take(t["trace_id"], "random")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(existing + list(picked), indent=2))
    reasons: dict[str, int] = {}
    for why in picked.values():
        key = "cluster" if why.startswith("cluster") else why
        reasons[key] = reasons.get(key, 0) + 1
    print(f"Added {len(picked)} traces to {out_path} ({', '.join(f'{v} {k}' for k, v in reasons.items())}).")


if __name__ == "__main__":
    main()
