"""first-trace templates: local exporter, env-var switch, normalizer, replay."""

from __future__ import annotations

import os
import sys
import textwrap

import pytest
from conftest import read_jsonl, run_py, template

pytest.importorskip("confident_trace")

APP = textwrap.dedent(
    """
    import confident_trace as ct
    from eval_tracing import setup_tracing, trace_mode

    print("MODE", trace_mode())
    setup_tracing("demo", instrumentations=())

    @ct.span(type="tool")
    def lookup_order(order_id):
        return {"status": "delivered"}

    @ct.span(name="answer", type="agent")
    def answer(question):
        ct.update_trace(input=question, thread_id="conv-1", tags=["orders"])
        status = lookup_order("A17")["status"]
        reply = f"Order A17 is {status}. <script>alert(1)</script>"
        ct.update_trace(output=reply)
        return reply

    answer("Where is order A17?")
    ct.shutdown()
    """
)


@pytest.fixture
def traced_project(project):
    for name in ("eval_tracing.py", "local_exporter.py"):
        (project / name).write_text(template("eval-trace", "python", name).read_text())
    (project / "app.py").write_text(APP)
    env = {**os.environ, "EVAL_SKILLS_TRACE_MODE": "local"}
    env.pop("CONFIDENT_API_KEY", None)
    out = run_py(project / "app.py", cwd=project, env=env)
    assert "MODE local" in out.stdout
    return project


def test_local_exporter_writes_otlp_json(traced_project):
    files = list((traced_project / ".eval/default/traces").glob("spans-*.jsonl"))
    assert len(files) == 1
    batches = read_jsonl(files[0])
    spans = [s for b in batches for rs in b["resourceSpans"] for ss in rs["scopeSpans"] for s in ss["spans"]]
    assert {s["name"] for s in spans} >= {"answer"}
    assert all(len(s["traceId"]) == 32 and len(s["spanId"]) == 16 for s in spans)
    assert len({s["traceId"] for s in spans}) == 1


def test_normalizer_builds_review_record(traced_project):
    run_py(template("eval-trace", "python", "normalize_traces.py"), cwd=traced_project)
    (record,) = read_jsonl(traced_project / ".eval/default/traces/traces.jsonl")
    assert record["input"] == "Where is order A17?"
    assert record["output"].startswith("Order A17 is delivered.")
    assert record["thread_id"] == "conv-1"
    assert record["tags"] == ["orders"]
    assert [s["type"] for s in record["steps"]] == ["tool"]
    assert record["steps"][0]["name"] == "lookup_order"
    assert record["steps"][0]["output"] == {"status": "delivered"}


def test_trace_mode_defaults(monkeypatch, tmp_path):
    for name in ("eval_tracing.py", "local_exporter.py"):
        (tmp_path / name).write_text(template("eval-trace", "python", name).read_text())
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("eval_tracing", None)
    import eval_tracing

    monkeypatch.delenv("EVAL_SKILLS_TRACE_MODE", raising=False)
    monkeypatch.delenv("CONFIDENT_API_KEY", raising=False)
    assert eval_tracing.trace_mode() == "local"
    monkeypatch.setenv("CONFIDENT_API_KEY", "x")
    assert eval_tracing.trace_mode() == "local"
    monkeypatch.setenv("EVAL_SKILLS_TRACE_MODE", "off")
    assert eval_tracing.trace_mode() == "off"


def test_replay_dry_run(traced_project):
    out = run_py(template("eval-trace", "python", "replay_spans.py"), "--dry-run", cwd=traced_project)
    assert "Would send 1 export batches" in out.stdout


def test_replay_requires_key(traced_project):
    env = {k: v for k, v in os.environ.items() if k != "CONFIDENT_API_KEY"}
    out = run_py(template("eval-trace", "python", "replay_spans.py"), cwd=traced_project, env=env, check=False)
    assert out.returncode != 0 and "CONFIDENT_API_KEY" in out.stderr
