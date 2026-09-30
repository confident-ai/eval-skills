"""Write finished OpenTelemetry spans to local JSON Lines files.

Each line is one OTLP/JSON ``ExportTraceServiceRequest`` (the same shape an
OTLP/HTTP collector accepts with ``Content-Type: application/json``), so the
files can be replayed to any OTLP endpoint later, including Confident AI.

Part of eval-skills (Apache-2.0). Copy into your project; no extra
dependencies beyond ``confident-trace``.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


def _any_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, (list, tuple)):
        return {"arrayValue": {"values": [_any_value(v) for v in value]}}
    return {"stringValue": str(value)}


def _attributes(attributes: Any) -> list[dict[str, Any]]:
    return [{"key": k, "value": _any_value(v)} for k, v in (attributes or {}).items()]


def _span(span: ReadableSpan) -> dict[str, Any]:
    ctx = span.get_span_context()
    out: dict[str, Any] = {
        "traceId": f"{ctx.trace_id:032x}",
        "spanId": f"{ctx.span_id:016x}",
        "name": span.name,
        # OTLP numbers SpanKind from UNSPECIFIED=0; the SDK starts at INTERNAL=0.
        "kind": span.kind.value + 1,
        "startTimeUnixNano": str(span.start_time or 0),
        "endTimeUnixNano": str(span.end_time or 0),
        "attributes": _attributes(span.attributes),
        "status": {"code": span.status.status_code.value},
    }
    if span.parent is not None:
        out["parentSpanId"] = f"{span.parent.span_id:016x}"
    if span.status.description:
        out["status"]["message"] = span.status.description
    if span.events:
        out["events"] = [
            {
                "timeUnixNano": str(event.timestamp),
                "name": event.name,
                "attributes": _attributes(event.attributes),
            }
            for event in span.events
        ]
    return out


def to_otlp_json(spans: Sequence[ReadableSpan]) -> dict[str, Any]:
    """Group spans by resource and instrumentation scope, as OTLP does."""
    resources: dict[int, dict[str, Any]] = {}
    for span in spans:
        resource_key = id(span.resource)
        entry = resources.setdefault(
            resource_key,
            {
                "resource": {"attributes": _attributes(span.resource.attributes)},
                "scopes": {},
            },
        )
        scope = span.instrumentation_scope
        scope_key = (scope.name, scope.version) if scope else ("", None)
        scope_entry = entry["scopes"].setdefault(
            scope_key,
            {"scope": {"name": scope_key[0], "version": scope_key[1] or ""}, "spans": []},
        )
        scope_entry["spans"].append(_span(span))
    return {
        "resourceSpans": [
            {"resource": entry["resource"], "scopeSpans": list(entry["scopes"].values())}
            for entry in resources.values()
        ]
    }


class JsonlSpanExporter(SpanExporter):
    """Append each exported batch of spans to ``<directory>/spans-YYYY-MM-DD.jsonl``."""

    def __init__(self, directory: str | Path = ".eval/default/traces") -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if not spans:
            return SpanExportResult.SUCCESS
        try:
            line = json.dumps(to_otlp_json(spans), ensure_ascii=False, separators=(",", ":"))
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            with self._lock, (self._directory / f"spans-{day}.jsonl").open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            return SpanExportResult.SUCCESS
        except Exception:  # never break the application because of tracing
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
