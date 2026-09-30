<!-- Synced from shared/trace-schema.md by scripts/sync_shared.py. Edit shared/trace-schema.md, not this copy. -->

# Local trace schema

Local tracks store traces as JSON Lines under `.eval/default/traces/`. There are two
layers:

1. **Raw spans** (`.eval/default/traces/spans-*.jsonl`), written by the local
   exporter template in `first-trace`. One line per finished OpenTelemetry
   span, in the OTLP/JSON span shape plus its resource attributes. Keep these:
   they can be replayed to any OTLP endpoint later, including Confident AI.
2. **Review records** (`.eval/default/traces/traces.jsonl`), one line per trace,
   produced by `normalize_traces` from the raw spans (or by a one-off
   converter when traces come from another tool). This is what the review app,
   the dataset builder, and the eval runner read.

## Review record

```json
{
  "trace_id": "5b8aa5a2d2c872e8321cf37308d69df2",
  "thread_id": "conversation-42",
  "started_at": "2026-09-30T12:00:00Z",
  "duration_ms": 1830,
  "input": "Can I return shoes after 45 days?",
  "output": "Returns are accepted within 30 days of delivery…",
  "tags": ["returns"],
  "metadata": { "environment": "staging", "user_id": "u_123" },
  "steps": [
    { "type": "llm", "name": "chat gpt-4.1-mini", "input": "…", "output": "…",
      "model": "gpt-4.1-mini", "input_tokens": 812, "output_tokens": 96 },
    { "type": "retriever", "name": "search_policies", "input": "return window",
      "output": ["Returns are accepted within 30 days…"] },
    { "type": "tool", "name": "lookup_order", "input": { "order_id": "A17" },
      "output": { "status": "delivered" } }
  ],
  "error": null
}
```

| Field | Required | Meaning |
|---|---|---|
| `trace_id` | yes | Stable id. Use the OTel trace id when there is one. |
| `input` / `output` | yes | What the user sent and what the app returned, as text or JSON. |
| `thread_id` | no | Groups turns of one conversation. |
| `steps` | no | Ordered spans below the entry point: `llm`, `retriever`, `tool`, `agent`, or `custom`. |
| `tags` | no | Short labels; `tags[0]` is the primary grouping key. |
| `metadata` | no | Anything else worth showing a reviewer. |
| `error` | no | Exception type if the request failed. |

## Mapping from OpenTelemetry

`confident-trace` records GenAI semantic conventions plus `confident.trace.*`
and `confident.span.*` attributes. The normalizer uses:

- the root span of each trace id as the entry point;
- `confident.trace.input` / `confident.trace.output` (or the root span's
  `confident.span.input` / `confident.span.output`) for `input` / `output`;
- `confident.trace.thread_id` or `gen_ai.conversation.id` for `thread_id`;
- `confident.span.type` for step type, falling back to `llm` when
  `gen_ai.operation.name` is `chat` or `text_completion`;
- `gen_ai.request.model`, `gen_ai.usage.input_tokens`,
  `gen_ai.usage.output_tokens` for model and usage.

Attribute names can evolve with the SDK. If a field comes out empty, print one
raw span and adjust the mapping rather than guessing.

## Converting from other tools

Traces already in Langfuse, LangSmith, Phoenix, Braintrust, or application
logs: export them to JSON, then write a short converter to review records.
Keep the original ids in `metadata.source_id` so annotations can be traced
back.
