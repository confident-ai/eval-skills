"""Keep installed skills self-contained; canonical shared prose lives in docs/."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
EXTRA = {
    "eval-start": [], "eval-audit": [], "eval-trace": ["capture", "integrations"],
    "eval-discover": ["data-sourcing", "local-review"],
    "eval-error-analysis": ["error-analysis", "local-review"],
    "eval-dataset": ["data-sourcing", "artifacts"],
    "eval-grade": ["calibration", "deepeval", "other-graders"],
    "eval-run": ["execution", "artifacts"],
    "eval-descent": ["experiments", "execution"],
    "eval-maintain": ["maintenance"],
}

def sync(check=False):
    stale = []
    for skill, refs in EXTRA.items():
        for name in ["workflow", "managed", "portability", "toolkit", *refs]:
            src = ROOT / "docs" / (name + ".md")
            dst = ROOT / "skills" / skill / "references" / src.name
            content = src.read_bytes()
            if not dst.exists() or dst.read_bytes() != content:
                stale.append(str(dst.relative_to(ROOT)))
                if not check:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(content)
    resources = [(ROOT / "scripts/setup_workspace.py", ROOT / "skills" / skill / "scripts/setup_workspace.py") for skill in EXTRA]
    for src in (ROOT / "skills/eval-discover/templates").rglob("*"):
        if src.is_file() and "__pycache__" not in src.parts:
            resources.append((src, ROOT / "skills/eval-error-analysis/templates" / src.relative_to(ROOT / "skills/eval-discover/templates")))
    resources.append((ROOT / "skills/eval-grade/templates/grouped_split.py", ROOT / "skills/eval-descent/templates/grouped_split.py"))
    for name in ('eval_tracing.py','local_exporter.py'):
        resources.append((ROOT/'skills/eval-trace/templates/python'/name,ROOT/'examples/support-bot/tracing'/name))
    for src,dst in resources:
        content=src.read_bytes()
        if not dst.exists() or dst.read_bytes()!=content:
            stale.append(str(dst.relative_to(ROOT)))
            if not check:
                dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(content)
    return stale

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = sync(args.check)
    if args.check and stale:
        raise SystemExit("Out-of-sync references: " + ", ".join(stale))
    print("References consistent" if args.check else "References synchronized")
