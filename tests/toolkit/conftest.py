"""Shared fixtures: template paths and a scratch project directory."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


def template(skill: str, *parts: str) -> Path:
    return SKILLS.joinpath(skill, "templates", *parts)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """An empty project directory used as the working directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".eval/default").mkdir(parents=True)
    return tmp_path


def run_py(script: Path, *args: str, cwd: Path, env: dict | None = None, check: bool = True):
    return subprocess.run(
        [sys.executable, str(script), *args], cwd=cwd, env=env, capture_output=True, text=True, check=check
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
