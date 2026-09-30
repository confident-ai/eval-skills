"""Turn raw OTLP/JSON span files into one review record per trace.

    python normalize_traces.py [--in .eval/default/traces] [--out .eval/default/traces/traces.jsonl]

Reads every ``spans-*.jsonl`` written by ``local_exporter.py`` and writes
``traces.jsonl`` in the eval-skills review-record shape (see
references/trace-schema.md). Safe to re-run: the output is rebuilt each time.

Part of eval-skills (Apache-2.0). Standard library only.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _value(v: dict[str, Any]) -> Any:
    if "stringValue" in v:
        return v["stringValue"]
    if "boolValue" in v:
        return v["boolValue"]
    if "intValue" in v:
        return int(v["intValue"])
    if "doubleValue" in v:
        return v["doubleValue"]
    if "arrayValue" in v:
        return [_value(x) for x in v["arrayValue"].get("values", [])]
    if "kvlistValue" in v:
        return {kv["key"]: _value(kv["value"]) for kv in v["kvlistValue"].get("values", [])}
    return None


def _attrs(items: list[dict[str, Any]] | None) -> dict[str, Any]:
    return {item["key"]: _value(item["value"]) for item in items or []}


def _decode(value: Any) -> Any:
    """Content attributes are JSON-encoded; decode when possible."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _unwrap_call(value: Any) -> Any:
    """Decorated functions record their arguments; show the useful part.

    Python records {"args": [...], "kwargs": {...}}; TypeScript records [...].
    """
    if isinstance(value, dict) and set(value) == {"args", "kwargs"}:
        args, kwargs = value["args"], value["kwargs"]
        if len(args) == 1 and not kwargs:
            return args[0]
        if not args:
            return kwargs
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def _step_type(a: dict[str, Any]) -> str:
    if a.get("confident.span.type"):
        return str(a["confident.span.type"])
    op = a.get("gen_ai.operation.name")
    if op in {"chat", "text_completion", "generate_content"}:
        return "llm"
    if op == "execute_tool":
        return "tool"
    if op == "invoke_agent":
        return "agent"
    return "custom"


def load_spans(traces_dir: Path) -> dict[str, list[dict[str, Any]]]:
    by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(traces_dir.glob("spans-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            for rs in payload.get("resourceSpans", []):
                resource = _attrs(rs.get("resource", {}).get("attributes"))
                for ss in rs.get("scopeSpans", []):
                    for span in ss.get("spans", []):
                        span = dict(span, _attrs=_attrs(span.get("attributes")), _resource=resource)
                        by_trace[span["traceId"]].append(span)
    return by_trace


def to_record(trace_id: str, spans: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {s["spanId"] for s in spans}
    roots = [s for s in spans if not s.get("parentSpanId") or s["parentSpanId"] not in ids]
    root = min(roots or spans, key=lambda s: int(s["startTimeUnixNano"]))
    ra = root["_attrs"]
    trace_attrs: dict[str, Any] = {}
    for s in spans:  # trace-level fields can be set on any span; the root wins ties
        for k, v in s["_attrs"].items():
            if k.startswith("confident.trace.") and (k not in trace_attrs or s is root):
                trace_attrs[k] = v

    start = int(root["startTimeUnixNano"])
    end = max(int(s["endTimeUnixNano"]) for s in spans)
    steps = []
    for s in sorted(spans, key=lambda s: int(s["startTimeUnixNano"])):
        if s is root:
            continue
        a = s["_attrs"]
        step: dict[str, Any] = {"type": _step_type(a), "name": a.get("gen_ai.tool.name") or s["name"]}
        step["input"] = _unwrap_call(
            _decode(a.get("confident.span.input", a.get("gen_ai.input.messages")))
        )
        step["output"] = _decode(a.get("confident.span.output", a.get("gen_ai.output.messages")))
        if a.get("gen_ai.system_instructions"):
            step["system"] = _decode(a["gen_ai.system_instructions"])
        for src, dst in (
            ("gen_ai.response.model", "model"),
            ("gen_ai.request.model", "model"),
            ("gen_ai.usage.input_tokens", "input_tokens"),
            ("gen_ai.usage.output_tokens", "output_tokens"),
        ):
            if src in a and dst not in step:
                step[dst] = a[src]
        if s.get("status", {}).get("code") == 2:
            step["error"] = s["status"].get("message") or a.get("error.type") or "error"
        steps.append(step)

    tags = trace_attrs.get("confident.trace.tags") or []
    metadata = _decode(trace_attrs.get("confident.trace.metadata")) or {}
    for key in ("environment", "user_id", "customer_id"):
        if trace_attrs.get(f"confident.trace.{key}"):
            metadata[key] = trace_attrs[f"confident.trace.{key}"]
    if root["_resource"].get("service.name"):
        metadata.setdefault("service", root["_resource"]["service.name"])

    return {
        "trace_id": trace_id,
        "thread_id": trace_attrs.get("confident.trace.thread_id") or ra.get("gen_ai.conversation.id"),
        "started_at": datetime.fromtimestamp(start / 1e9, tz=timezone.utc).isoformat(),
        "duration_ms": round((end - start) / 1e6, 1),
        "name": trace_attrs.get("confident.trace.name") or root["name"],
        "input": _unwrap_call(_decode(trace_attrs.get("confident.trace.input", ra.get("confident.span.input")))),
        "output": _decode(trace_attrs.get("confident.trace.output", ra.get("confident.span.output"))),
        "tags": tags if isinstance(tags, list) else [tags],
        "metadata": metadata,
        "steps": steps,
        "error": (root.get("status", {}).get("message") or "error") if root.get("status", {}).get("code") == 2 else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="src", default=".eval/default/traces")
    parser.add_argument("--out", dest="dst", default=None)
    args = parser.parse_args()
    src = Path(args.src)
    dst = Path(args.dst) if args.dst else src / "traces.jsonl"
    records = [to_record(tid, spans) for tid, spans in load_spans(src).items()]
    records.sort(key=lambda r: r["started_at"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    print(f"Wrote {len(records)} traces to {dst}")


if __name__ == "__main__":
    main()
