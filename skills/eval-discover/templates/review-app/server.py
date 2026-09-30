"""Local trace review server for eval-skills. Python standard library only.

    python server.py --traces .eval/default/traces/traces.jsonl --dir .eval/default/review-app [--port 8765] [--mode review|label]

Serves the review app on 127.0.0.1 and stores everything under --dir:

    samples.json         trace ids to review, in order (written by the agent; all traces if absent)
    annotations.json     {trace_id: {verdict, note, labels, updated_at}} (written by this server)
    failure_modes.json   [{id, definition, count, examples}] (written by the agent, shown read-only)

Security: binds to 127.0.0.1 only, rejects requests whose Host header isn't
this server, requires a per-session token on every write, and sends a strict
Content-Security-Policy. Trace content is untrusted; the app renders it as
text only.

Part of eval-skills (Apache-2.0).
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
}
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
MAX_BODY = 1_000_000
VERDICTS = {None, "pass", "fail", "defer", "uncertain"}

class Conflict(ValueError):
    pass


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default


def _write_json_atomic(path: Path, data) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0.0


class ReviewStore:
    def __init__(self, traces: Path, directory: Path, mode: str) -> None:
        self.traces_path = traces
        self.dir = directory
        self.mode = mode
        self.lock = threading.Lock()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.annotations_path = self.dir / "annotations.json"
        self.samples_path = self.dir / "samples.json"
        self.modes_path = self.dir / "failure_modes.json"
        self.taxonomy_path = self.dir / "taxonomy.json"

    def traces(self) -> list[dict]:
        records = {}
        if self.traces_path.exists():
            for line in self.traces_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    record = json.loads(line)
                    records[str(record["trace_id"])] = record
        sample = _read_json(self.samples_path, None)
        if isinstance(sample, list):
            return [records[i] for i in map(str, sample) if i in records]
        return list(records.values())

    def meta(self) -> dict:
        return {
            "mode": self.mode,
            "version": [_mtime(self.traces_path), _mtime(self.samples_path), _mtime(self.modes_path), _mtime(self.taxonomy_path)],
        }

    def data(self) -> dict:
        return {
            **self.meta(),
            "traces": self.traces(),
            "annotations": _read_json(self.annotations_path, {}),
            "failure_modes": self.taxonomy()["modes"],
            "taxonomy": self.taxonomy(),
        }

    def annotate(self, payload: dict) -> dict:
        trace_id = payload.get("trace_id")
        verdict = payload.get("verdict")
        note = payload.get("note", "")
        labels = payload.get("labels", {})
        if not isinstance(trace_id, str) or not trace_id:
            raise ValueError("trace_id is required")
        if not isinstance(payload, dict):
            raise ValueError("object required")
        if trace_id not in {t["trace_id"] for t in self.traces()}:
            raise ValueError("unknown trace")
        reviewer = payload.get("reviewed_by")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError("reviewed_by is required")
        if verdict not in VERDICTS:
            raise ValueError("verdict must be pass, fail, defer, or null")
        if not isinstance(note, str) or len(note) > 20_000:
            raise ValueError("note must be a string under 20k characters")
        if not isinstance(labels, dict) or any(v not in (None, "pass", "fail", "uncertain") for v in labels.values()):
            raise ValueError("labels must map failure-mode ids to pass, fail, or null")
        with self.lock:
            annotations = _read_json(self.annotations_path, {})
            current = annotations.get(trace_id, {})
            if payload.get("revision") != current.get("revision", 0):
                raise Conflict("Stale annotation; reload before saving")
            annotations[trace_id] = {
                "id": current.get("id", "note:" + trace_id),
                "case_id": next((t.get("case_id", trace_id) for t in self.traces() if t["trace_id"] == trace_id), trace_id),
                "origin": current.get("origin", "human"),
                "reviewed_by": reviewer,
                "revision": current.get("revision", 0) + 1,
                "verdict": verdict,
                "note": note,
                "labels": {k: v for k, v in labels.items() if v is not None},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _write_json_atomic(self.annotations_path, annotations)
            return annotations[trace_id]

    def taxonomy(self):
        return _read_json(self.taxonomy_path, {"revision": 0, "modes": _read_json(self.modes_path, []), "assignments": [], "history": []})

    def save_taxonomy(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("object required")
        with self.lock:
            current = self.taxonomy()
            if payload.get("revision") != current["revision"]:
                raise Conflict("Stale taxonomy; reload before saving")
            modes, assignments = payload.get("modes"), payload.get("assignments")
            reviewer = payload.get("reviewed_by")
            if not isinstance(reviewer, str) or not reviewer.strip():
                raise ValueError("reviewed_by is required")
            if not isinstance(modes, list) or not isinstance(assignments, list):
                raise ValueError("modes and assignments must be lists")
            ids = set()
            for mode in modes:
                if not isinstance(mode, dict) or not isinstance(mode.get("id"), str) or not mode["id"] or mode["id"] in ids:
                    raise ValueError("unique nonempty mode IDs required")
                ids.add(mode["id"])
                if not isinstance(mode.get("definition"), str) or not mode["definition"].strip():
                    raise ValueError("mode definition required")
                if mode.get("status", "proposed") not in {"proposed", "confirmed", "retired"}:
                    raise ValueError("invalid mode status")
            annotations = _read_json(self.annotations_path, {})
            known = {v.get("id", "note:" + k): (k, v) for k, v in annotations.items()}
            seen = set()
            for a in assignments:
                if not isinstance(a, dict) or not a.get("id") or a["id"] in seen:
                    raise ValueError("unique assignment IDs required")
                seen.add(a["id"])
                if a.get("annotation_id") not in known:
                    raise ValueError("assignment must reference an existing annotation")
                trace_id, note = known[a["annotation_id"]]
                if a.get("trace_id") != trace_id or a.get("case_id") != note.get("case_id", trace_id):
                    raise ValueError("assignment evidence mismatch")
                if a.get("status") not in {"suggested", "confirmed", "rejected", "uncertain"}:
                    raise ValueError("invalid assignment status")
                if a.get("mode_id") not in ids and not (a.get("mode_id") is None and a["status"] == "uncertain"):
                    raise ValueError("unknown mode")
            # Record human confirmation separately for definitions and memberships.
            now = datetime.now(timezone.utc).isoformat()
            for key, records in (("modes", modes), ("assignments", assignments)):
                old = {x["id"]: x for x in current[key]}
                for item in records:
                    if item.get("status") == "confirmed":
                        prior = old.get(item["id"], {})
                        changed = any(item.get(k) != prior.get(k) for k in ("definition", "mode_id", "annotation_id"))
                        item["reviewed_by"] = reviewer if changed or prior.get("status") != "confirmed" else prior.get("reviewed_by", reviewer)
                        item["reviewed_at"] = now if changed or prior.get("status") != "confirmed" else prior.get("reviewed_at", now)
            value = {"revision": current["revision"] + 1, "modes": modes, "assignments": assignments,
                     "history": current.get("history", []) + [{"revision": current["revision"], "modes": current["modes"], "assignments": current["assignments"], "action": payload.get("action", "edit"), "reviewed_by": reviewer, "at": now}]}
            _write_json_atomic(self.taxonomy_path, value)
            return value


def make_handler(store: ReviewStore, token: str, allowed_hosts: set[str], static_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "eval-skills-review"

        def log_message(self, fmt, *args):  # keep the terminal quiet
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in allowed_hosts

        def do_GET(self) -> None:
            if not self._host_ok():
                return self._json(HTTPStatus.FORBIDDEN, {"error": "unexpected Host header"})
            path = self.path.split("?", 1)[0]
            if path in STATIC:
                name, content_type = STATIC[path]
                body = (static_dir / name).read_bytes()
                if name == "index.html":
                    body = body.replace(b"__SESSION_TOKEN__", token.encode())
                return self._send(HTTPStatus.OK, body, content_type)
            if path == "/api/data":
                return self._json(HTTPStatus.OK, store.data())
            if path == "/api/export":
                return self._json(HTTPStatus.OK, store.data())
            if path == "/api/meta":
                return self._json(HTTPStatus.OK, store.meta())
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._host_ok():
                return self._json(HTTPStatus.FORBIDDEN, {"error": "unexpected Host header"})
            if not secrets.compare_digest(self.headers.get("X-Session-Token", ""), token):
                return self._json(HTTPStatus.FORBIDDEN, {"error": "missing or wrong session token"})
            if self.path not in {"/api/annotations", "/api/taxonomy"}:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "send application/json"})
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "bad body size"})
            try:
                payload = json.loads(self.rfile.read(length))
                saved = store.annotate(payload) if self.path == "/api/annotations" else store.save_taxonomy(payload)
            except Conflict as err:
                return self._json(HTTPStatus.CONFLICT, {"error": str(err)})
            except (ValueError, TypeError, AttributeError) as err:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": str(err)})
            return self._json(HTTPStatus.OK, saved)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="eval-skills local review app")
    parser.add_argument("--traces", default=".eval/default/traces/traces.jsonl")
    parser.add_argument("--dir", default=".eval/default/review-app")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--mode", choices=["review", "label"], default="review")
    parser.add_argument("--static", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args()

    store = ReviewStore(Path(args.traces), Path(args.dir), args.mode)
    token = secrets.token_urlsafe(24)
    hosts = {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}
    handler = make_handler(store, token, hosts, Path(args.static))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Review app ({args.mode} mode): http://127.0.0.1:{args.port}/  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
