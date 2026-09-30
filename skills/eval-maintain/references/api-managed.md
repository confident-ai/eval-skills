> Operation names were checked against the available MCP inventory on 2026-09-30; individual REST recipes and live calls remain untested. Every MCP call except `list_projects` requires the selected `project_id`. Prefer the connected tool schema over spellings in examples.

# Monitor production: managed on Confident AI

Confident AI runs **online evals**: every traced request that matches an
evaluation rule is graded by a metric collection as it arrives, with no job
to run.

## Set up an evaluation rule

`create_evaluation_rule` with:

- `name`: for example `"prod: support-bot-core"`;
- `data_model`: `"TRACE"` (each request), `"THREAD"` (whole conversations),
  or `"SPAN"` (a specific step, with `span_type` such as `"RETRIEVER"`,
  `"TOOL"`, `"LLM"`, or `"AGENT"`);
- `metric_collection`: the validated collection from `eval-grade`
  (drop metrics that need `expected_output`, which live traffic lacks);
- `sample_rate`: the fraction of matching traffic to grade (Step 1 of the
  skill);
- `filters`: restrict to `environment = production`, a release, or a
  customer segment;
- `thread_timelimit` (threads only): how long a conversation must be quiet
  before it's graded as finished.

Manage rules with `list_evaluation_rules`, `update_evaluation_rule` (for
example to change `sample_rate` or turn `enabled` off), and
`delete_evaluation_rule`. Record the rule ids in
`managed.evaluation_rule_ids`.

## Watch and alert

Results appear on the traces themselves and in the project's dashboards,
split by metric, environment, and time. Show the user where they are, and
suggest setting alerts on the metrics that matter most (a pass rate below
its usual band, a spike in errors) in the project's settings.

To grade a specific past trace or conversation on demand (for example the one
a customer complained about), use `evaluate_trace` / `evaluate_thread`.

## Close the loop

When a metric drops or traffic shifts, add recent production traces to a new
annotation queue (`create_annotation_queue`, `add_items_to_annotation_queue`)
and run `eval-error-analysis` on them. New failure modes become new metrics,
validated before they're added to the rule's collection.
