"""Build a static HTML report from .eval/default/runs/*/ (results.jsonl + summary.json).

    python report.py [--runs .eval/default/runs] [--out .eval/default/runs/report.html]

One page, no JavaScript, no external assets. Every piece of case text is
HTML-escaped: inputs and outputs are untrusted.

Part of eval-skills (Apache-2.0). Standard library only.
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

CSS = """
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:24px;color:#1d1d1b;background:#f7f7f5}
h1{font-size:20px}h2{font-size:16px;margin-top:28px}
table{border-collapse:collapse;background:#fff;width:100%}th,td{border:1px solid #e2e1dc;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f0efea;font-weight:600}.num{text-align:right;font-variant-numeric:tabular-nums}
.pass{color:#1f7a4d}.fail{color:#b3261e}.muted{color:#6b6b66}
pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:4px 0;font:12px/1.4 ui-monospace,Menlo,monospace;background:#f7f7f5;padding:6px;border-radius:4px}
details summary{cursor:pointer}
@media (prefers-color-scheme:dark){body{background:#161615;color:#ecebe6}table{background:#1f1f1d}th{background:#262624}th,td{border-color:#33332f}pre{background:#161615}}
"""


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.0f}%"


def text(value, limit=4000) -> str:
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return escape(s if len(s) <= limit else s[:limit] + " …")


def build(runs_dir: Path) -> str:
    variants = sorted(
        [p for p in runs_dir.iterdir() if (p / "results.jsonl").exists()],
        key=lambda p: (p.name != "baseline", p.name),
    )
    summaries = {v.name: json.loads((v / "summary.json").read_text()) if (v / "summary.json").exists() else {} for v in variants}
    rows = {v.name: read_jsonl(v / "results.jsonl") for v in variants}
    modes = sorted({m for s in summaries.values() for m in (s.get("per_failure_mode") or {})})

    out = [f"<!doctype html><html lang=en><head><meta charset=utf-8>",
           "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\">",
           f"<title>Eval report</title><style>{CSS}</style></head><body><h1>Eval report</h1>",
           "<p class=muted>Pass = the failure mode was not observed. Intervals are 95%. "
           "Differences inside the interval are noise, not wins.</p>",
           "<h2>Runs</h2><table><tr><th>Variant</th><th class=num>All pass</th><th>95% CI</th>"]
    out += [f"<th class=num>{escape(m)}</th>" for m in modes]
    out.append("<th class=num>p50 s</th><th class=num>p95 s</th><th class=num>Errors</th><th>vs baseline</th></tr>")
    for name, s in summaries.items():
        ci = s.get("ci95_all") or [None, None]
        cells = [f"<td>{escape(name)}</td><td class=num>{pct(s.get('pass_rate_all'))}</td>",
                 f"<td>{pct(ci[0])}–{pct(ci[1])}</td>"]
        cells += [f"<td class=num>{pct((s.get('per_failure_mode') or {}).get(m, {}).get('pass_rate'))}</td>" for m in modes]
        lat = s.get("latency_s") or {}
        err = s.get("errors") or {}
        cmp_ = s.get("compare") or {}
        verdict = (
            f"{cmp_['delta']:+.2f} ({cmp_['ci95'][0]:+.2f} to {cmp_['ci95'][1]:+.2f}): {escape(cmp_['verdict'])}"
            if cmp_.get("n_cases") else "–"
        )
        cells.append(f"<td class=num>{lat.get('p50', '–')}</td><td class=num>{lat.get('p95', '–')}</td>")
        cells.append(f"<td class=num>{err.get('app', 0) + err.get('grader', 0)}</td><td>{verdict}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")

    case_ids = sorted({r["case_id"] for rs in rows.values() for r in rs})
    out.append("<h2>Cases</h2><table><tr><th>Case</th><th>Tag</th>")
    out += [f"<th class=num>{escape(v)}</th>" for v in rows]
    out.append("</tr>")
    for cid in case_ids:
        by_variant = {v: [r for r in rs if r["case_id"] == cid] for v, rs in rows.items()}
        first = next(r for rs in by_variant.values() for r in rs)
        tag = (first.get("tags") or ["–"])[0]
        cells = [f"<td><details><summary>{escape(str(cid))}</summary><pre>{text(first.get('input'))}</pre>"]
        for v, rs in by_variant.items():
            for r in rs:
                reasons = "".join(
                    f"<div class={'pass' if g['passed'] else 'fail'}>{escape(m)}: {escape(str(g.get('reason') or ''))}</div>"
                    for m, g in r["grades"].items()
                )
                cells.append(f"<div class=muted>{escape(v)} rep {r['rep']}</div><pre>{text(r.get('output'))}</pre>{reasons}")
        cells.append(f"</details></td><td>{escape(str(tag))}</td>")
        for v, rs in by_variant.items():
            if rs:
                p = sum(r["passed_all"] for r in rs) / len(rs)
                cells.append(f"<td class='num {'pass' if p == 1 else 'fail' if p == 0 else ''}'>{p:.0%}</td>")
            else:
                cells.append("<td class=num>–</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table></body></html>")
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", default=".eval/default/runs")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    runs = Path(args.runs)
    out = Path(args.out) if args.out else runs / "report.html"
    out.write_text(build(runs), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
