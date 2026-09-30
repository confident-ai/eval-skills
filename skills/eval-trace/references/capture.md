# First-trace recipes

Use the existing app runtime and dependency manager. Inspect installed confident-trace versions and current [Python](https://github.com/confident-ai/confident-trace/tree/main/python) or [TypeScript](https://github.com/confident-ai/confident-trace/tree/main/typescript) docs before adapting a recipe. Do not force installation when existing logs already provide adequate evidence.

## Local Python capture with no hosted export

A supported custom exporter can keep first evidence local. This example uses the OTel console exporter as a JSON-record stream. Its output is not JSONL; preserve it as the original export or parse it with an explicit adapter.

```python
from pathlib import Path
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
import confident_trace as ct

# Adapt the import to the actual application. Run with a non-sensitive example.
with Path("first-trace.jsonstream").open("w") as stream:
    ct.init(exporter=ConsoleSpanExporter(out=stream))
    from app import run_agent  # Import after initialization where hooks require it.
    try:
        with ct.span("first-eval", type="agent", input="A representative request"):
            output = run_agent("A representative request")
            ct.update_trace(input="A representative request", output=output)
    finally:
        ct.shutdown()  # Flush while the file remains open.
```

The app import is illustrative, not a runnable universal entrypoint. Initialize before provider aliases are cached where an integration needs that. If the app already owns a global OTel provider, attach a local processor through that provider's supported lifecycle instead of replacing it. Verify actual spans; an init call alone does not prove instrumentation worked.

## Local TypeScript capture

With supported Node and SDK versions, inject a local exporter:

```typescript
import { init } from "confident-trace";
import { InMemorySpanExporter } from "@opentelemetry/sdk-trace-base";
import { writeFile } from "node:fs/promises";

const exporter = new InMemorySpanExporter();
const tracing = init({ exporter });
// Invoke the actual application here; await all work and close streams.
await tracing.flush();
const records = exporter.getFinishedSpans().map(span => ({
  name: span.name,
  context: span.spanContext(),
  parent: span.parentSpanContext,
  attributes: span.attributes,
  events: span.events,
  status: span.status,
  startTime: span.startTime,
  endTime: span.endTime,
}));
await writeFile("first-trace.json", JSON.stringify(records, null, 2));
await tracing.shutdown();
```

For automatic instrumentation launch the app with the documented `node --import confident-trace/register ...` preload as well as calling `init()`. Adapt the projection to retain parent identity from the installed OTel version. In an existing provider, use its processor/flush lifecycle. In bundled apps, use documented manual adapters when the preload cannot intercept bundled imports. Never treat an empty exported array as a successful first trace.

## Connect after inspection

Configure `CONFIDENT_API_KEY` in the environment. Use the documented `CONFIDENT_OTEL_ENDPOINT` for a non-default region or collector; do not guess regional endpoints. Switch the local-only exporter to the supported hosted configuration after the user selects managed. Keep credentials out of saved traces and code.

Inspect content policy before exporting. Default capture limits can truncate long prompts and tool output; third-party spans can have separate redaction rules. Retain necessary larger artifacts through approved local references or platform attachments, not invented inline fields.

Check one request for matching input/output, correct hierarchy, tool activity, model metadata, nonzero measured duration, and usage when the provider returns it. Token omissions and binary omissions should be declared. No trace API exposes hidden model reasoning that was not returned.
