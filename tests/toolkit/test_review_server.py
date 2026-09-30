"""review-ui server.py: host check, session token, validation, CSP, storage."""

from __future__ import annotations

import http.client
import importlib.util
import json
import re
import threading
from http.server import ThreadingHTTPServer

import pytest
from conftest import template, write_jsonl


@pytest.fixture
def server(project):
    spec = importlib.util.spec_from_file_location("review_server", template("eval-discover", "review-app", "server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    write_jsonl(
        project / ".eval/default/traces/traces.jsonl",
        [{"trace_id": f"t{i}", "input": "<script>alert(1)</script>", "output": "ok", "steps": []} for i in range(3)],
    )
    store = mod.ReviewStore(project / ".eval/default/traces/traces.jsonl", project / ".eval/default/review-app", "review")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: None)
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = mod.make_handler(
        store, "tok123", {f"127.0.0.1:{port}", f"localhost:{port}"}, template("eval-discover", "review-app")
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield port, project
    httpd.shutdown()
    httpd.server_close()


def request(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read().decode()
    return resp.status, dict(resp.getheaders()), data


def test_page_has_token_and_csp(server):
    port, _ = server
    status, headers, body = request(port, "GET", "/")
    assert status == 200
    assert re.search(r'name="session-token" content="tok123"', body)
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_rejects_foreign_host(server):
    port, _ = server
    status, _, _ = request(port, "GET", "/api/data", headers={"Host": "evil.example:80"})
    assert status == 403


def test_write_requires_token(server):
    port, project = server
    body = {"trace_id": "t0", "verdict": "fail", "note": "wrong"}
    status, _, _ = request(port, "POST", "/api/annotations", body, {"Content-Type": "application/json"})
    assert status == 403
    status, _, _ = request(port, "POST", "/api/annotations", body, {"Content-Type": "application/json", "X-Session-Token": "nope"})
    assert status == 403
    assert not (project / ".eval/default/review-app/annotations.json").exists()


def test_saves_valid_annotation_and_rejects_invalid(server):
    port, project = server
    headers = {"Content-Type": "application/json", "X-Session-Token": "tok123"}
    ok = {"revision":0,"reviewed_by":"fixture-reviewer","trace_id": "t1", "verdict": "fail", "note": "invented a fee", "labels": {"invented-fee": "fail"}}
    status, _, _ = request(port, "POST", "/api/annotations", ok, headers)
    assert status == 200
    saved = json.loads((project / ".eval/default/review-app/annotations.json").read_text())
    assert saved["t1"]["verdict"] == "fail" and saved["t1"]["labels"] == {"invented-fee": "fail"}
    for bad in ({"trace_id": "t1", "verdict": "maybe"}, {"trace_id": "t1", "labels": {"x": "meh"}}, {"verdict": "pass"}):
        status, _, _ = request(port, "POST", "/api/annotations", bad, headers)
        assert status == 400


def test_samples_file_filters_and_orders(server):
    port, project = server
    (project / ".eval/default/review-app/samples.json").write_text(json.dumps(["t2", "t0", "missing"]))
    _, _, body = request(port, "GET", "/api/data")
    assert [t["trace_id"] for t in json.loads(body)["traces"]] == ["t2", "t0"]


def test_app_never_uses_inner_html():
    js = template("eval-discover", "review-app", "app.js").read_text()
    code = "\n".join(line for line in js.splitlines() if not line.strip().startswith("//"))
    assert "innerHTML" not in code and "eval(" not in code
