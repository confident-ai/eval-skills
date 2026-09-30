> Operation names were checked against the available MCP inventory on 2026-09-30; individual REST recipes and live calls remain untested. Every MCP call except `list_projects` requires the selected `project_id`. Prefer the connected tool schema over spellings in examples.

# Write graders: managed on Confident AI

On Confident AI, graders are **metrics**, grouped into a **metric
collection** that runs on datasets (offline) and on live traces (online).
Metrics run on the platform, so there's no grader code to maintain.

## 1. Start from the suggested metrics

Error Analysis already suggested a metric for each failure mode. Ask the user
to create the ones they agree with from the Error Analysis page, then read
them back with `list_metrics` or `get_metric` so you can check the wording
against the rules in [judge-prompts.md](judge-prompts.md).

## 2. Create or refine metrics yourself

For failure modes without a suitable suggestion, use `create_metric`:

- `name`: the failure mode id, for example `invented-policy`;
- `criteria`: the judge prompt's criterion plus pass and fail definitions,
  written as in [judge-prompts.md](judge-prompts.md);
- `evaluation_steps` (optional): explicit steps when the criterion needs a
  procedure ("1. List every window, fee, or rule stated in the actual
  output. 2. Check each against the retrieval context. 3. …");
- `evaluation_params`: only the fields the judge needs. Single-turn:
  `input`, `actualOutput`, `expectedOutput`, `context`, `retrievalContext`,
  `toolsCalled`, `expectedTools`. Multi-turn: `turns`, `scenario`,
  `expectedOutcome`, `role`, `content`;
- `multi_turn: true` for conversation-level metrics.

Use `update_metric` to revise. Criteria, steps, and rubric are replaced
wholesale, so always send the full text.

Code-checkable failure modes (format, required fields, forbidden phrases)
can still be expressed as metrics with precise criteria, but prefer fixing
them in the app with validation where you can; a hard check in the app beats
a grader that notices afterwards.

## 3. Group them into a collection

`create_metric_collection` with a `name` (for example `"support-bot-core"`),
`multiTurn` if needed, and `metricSettings`: one entry per metric with
`metric` (by name), `threshold`, and **`strictMode: true`**. Strict mode makes
each metric a pass/fail verdict instead of a sliding score, which is what
validation and reporting expect. Set `evaluationModelProvider` and
`evaluationModelName` per metric if the user wants a specific judge model.

Record `managed.metric_collection` in `.eval/default/workflow.json`.

## 4. Try it on known cases

Run the collection on a handful of reviewed traces with `evaluate_trace`
(single-turn) or `evaluate_thread` (conversations), passing the trace UUID or
thread id and the collection name. Compare each verdict with the reviewer's
annotation, and show the user both side by side. Fix disagreements before
moving on to `eval-grade`.
